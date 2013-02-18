import csv
import fnmatch
import json
import os
import re

from hashlib import md5
from django.core.urlresolvers import reverse

from odk_logger.models import XForm
from odk_logger.views import submission
from odk_viewer.models import DataDictionary
from odk_viewer.views import csv_export, xls_export
from test_base import MainTestCase


uuid_regex = re.compile(
    r'(</instance>.*uuid[^//]+="\')([^\']+)(\'".*)', re.DOTALL)


class TestSite(MainTestCase):

    def test_process(self, username=None, password=None):
        if username is not None:
            self._create_user_and_login(username, password)
        self._publish_xls_file()
        self._check_formList()
        self._download_xform()
        self._make_submissions()
        self._check_csv_export()
        self._check_delete()

    def test_uuid_submit(self):
        self._create_user_and_login()
        self._publish_xls_file()
        survey = 'transport_2011-07-25_19-05-49'
        path = os.path.join(
            self.this_directory, 'fixtures', 'transportation',
            'instances', survey, survey + '.xml')
        with open(path) as f:
            post_data = {'xml_submission_file': f, 'uuid': self.xform.uuid}
            url = '/submission'
            self.response = self.anon.post(url, post_data)

    def test_publish_xlsx_file(self):
        self._create_user_and_login()
        path = os.path.join(self.this_directory, 'fixtures', 'exp.xlsx')
        pre_count = XForm.objects.count()
        response = MainTestCase._publish_xls_file(self, path)
        # make sure publishing the survey worked
        self.assertEqual(response.status_code, 200)
        self.assertEqual(XForm.objects.count(), pre_count + 1)

    def test_google_url_upload(self):
        if self._internet_on(url="http://google.com"):
            self._create_user_and_login()
            xls_url = "https://docs.google.com/spreadsheet/pub?"\
                "key=0AvhZpT7ZLAWmdDhISGhqSjBOSl9XdXd5SHZHUUE2RFE&output=xls"
            pre_count = XForm.objects.count()
            response = self.client.post('/%s/' % self.user.username,
                                        {'xls_url': xls_url})
            # make sure publishing the survey worked
            self.assertEqual(response.status_code, 200)
            self.assertEqual(XForm.objects.count(), pre_count + 1)

    def test_url_upload(self):
        if self._internet_on(url="http://google.com"):
            self._create_user_and_login()
            xls_url = 'http://formhub.org' \
                      '/formhub_u/forms/tutorial/form.xls'
            pre_count = XForm.objects.count()
            response = self.client.post('/%s/' % self.user.username,
                                        {'xls_url': xls_url})
            # make sure publishing the survey worked
            self.assertEqual(response.status_code, 200)
            self.assertEqual(XForm.objects.count(), pre_count + 1)

    def test_bad_url_upload(self):
        if self._internet_on():
            self._create_user_and_login()
            xls_url = 'formhuborg/pld/forms/transportation_2011_07_25/form.xls'
            pre_count = XForm.objects.count()
            response = self.client.post('/%s/' % self.user.username,
                                        {'xls_url': xls_url})
            # make sure publishing the survey worked
            self.assertEqual(response.status_code, 200)
            self.assertEqual(XForm.objects.count(), pre_count)

    # This method tests a large number of xls files.
    # create a directory /main/test/fixtures/online_xls
    # containing the files you would like to test.
    # DO NOT CHECK IN PRIVATE XLS FILES!!
    def test_upload_all_xls(self):
        root_dir = os.path.join(self.this_directory, "fixtures", "online_xls")
        if os.path.exists(root_dir):
            success = True
            for root, sub_folders, filenames in os.walk(root_dir):
                # ignore files that don't end in '.xls'
                for filename in fnmatch.filter(filenames, '*.xls'):
                    success = self._publish_file(os.path.join(root, filename),
                                                 False)
                    if success:
                        # delete it so we don't have id_string conflicts
                        if self.xform:
                            self.xform.delete()
                            self.xform = None
                print 'finished sub-folder %s' % root
            self.assertEqual(success, True)

    def test_url_upload_non_dot_xls_path(self):
        if self._internet_on():
            self._create_user_and_login()
            xls_url = 'http://formhub.org/formhub_u/forms/tutorial/form.xls'
            pre_count = XForm.objects.count()
            response = self.client.post('/%s/' % self.user.username,
                                        {'xls_url': xls_url})
            # make sure publishing the survey worked
            self.assertEqual(response.status_code, 200)
            self.assertEqual(XForm.objects.count(), pre_count + 1)

    def test_not_logged_in_cannot_upload(self):
        path = os.path.join(self.this_directory, "fixtures", "transportation",
                            "transportation.xls")
        if not path.startswith('/%s/' % self.user.username):
            path = os.path.join(self.this_directory, path)
        with open(path) as xls_file:
            post_data = {'xls_file': xls_file}
            return self.anon.post('/%s/' % self.user.username, post_data)

    def _publish_file(self, xls_path, strict=True):
        """
        Returns False if not strict and publish fails
        """
        pre_count = XForm.objects.count()
        self.response = MainTestCase._publish_xls_file(self, xls_path)
        # make sure publishing the survey worked
        self.assertEqual(self.response.status_code, 200)
        if XForm.objects.count() != pre_count + 1:
            # print file location
            print '\nPublish Failure for file: %s' % xls_path
            if strict:
                self.assertEqual(XForm.objects.count(), pre_count + 1)
            else:
                return False
        self.xform = list(XForm.objects.all())[-1]
        return True

    def _publish_xls_file(self):
        xls_path = os.path.join(self.this_directory, "fixtures",
                                "transportation", "transportation.xls")
        self._publish_file(xls_path)
        self.assertEqual(self.xform.id_string, "transportation_2011_07_25")

    def _check_formList(self):
        url = '/%s/formList' % self.user.username
        response = self.anon.get(url)
        self.download_url = \
            'http://testserver/%s/forms/transportation_2011_07_25/form.xml'\
            % self.user.username
        self.manifest_url = \
            'http://testserver/%s/xformsManifest/transportation_2011_07_25'\
            % self.user.username
        md5_hash = md5(self.xform.xml).hexdigest()
        expected_content = """<?xml version='1.0' encoding='UTF-8' ?>

<xforms xmlns="http://openrosa.org/xforms/xformsList">

  <xform>
    <formID>transportation_2011_07_25</formID>
    <name>transportation_2011_07_25</name>
    <majorMinorVersion/>
    <version/>
    <hash>md5:%(hash)s</hash>
    <descriptionText></descriptionText>
    <downloadUrl>%(download_url)s</downloadUrl>
    <manifestUrl>%(manifest_url)s</manifestUrl>
  </xform>

</xforms>
""" % {'download_url': self.download_url, 'manifest_url': self.manifest_url,
       'hash': md5_hash}
        self.assertEqual(response.content, expected_content)
        self.assertTrue(response.has_header('X-OpenRosa-Version'))
        self.assertTrue(response.has_header('Date'))

    def _download_xform(self):
        response = self.anon.get(self.download_url)
        xml_path = os.path.join(self.this_directory, "fixtures",
                                "transportation", "transportation.xml")
        with open(xml_path) as xml_file:
            expected_content = xml_file.read()

        # check for UUID and remove
        split_response = uuid_regex.split(response.content)
        self.assertEqual(self.xform.uuid,
                         unicode(split_response[XForm.uuid_node_location]))

        # remove UUID
        split_response[XForm.uuid_node_location:XForm.uuid_node_location + 1] \
            = []

        # check content without UUID
        self.assertEqual(expected_content, ''.join(split_response))

    def _check_csv_export(self):
        self._check_data_dictionary()
        self._check_data_for_csv_export()
        self._check_group_xpaths_do_not_appear_in_dicts_for_export()
        self._check_csv_export_first_pass()
        self._check_csv_export_second_pass()

    def _check_data_dictionary(self):
        # test to make sure the data dictionary returns the expected headers
        qs = DataDictionary.objects.filter(user=self.user)
        self.assertEqual(qs.count(), 1)
        self.data_dictionary = DataDictionary.objects.all()[0]
        with open(os.path.join(self.this_directory, "fixtures",
                  "transportation", "headers.json")) as f:
            expected_list = json.load(f)
        self.assertEqual(self.data_dictionary.get_headers(), expected_list)

        # test to make sure the headers in the actual csv are as expected
        actual_csv = self._get_csv_()
        self.assertEqual(sorted(actual_csv.next()), sorted(expected_list))

    def _check_data_for_csv_export(self):
        data = [
            {"available_transportation_types_to_referral_facility/ambulance":
             True,
             "available_transportation_types_to_referral_facility/bicycle":
                True,
             "loop_over_transport_types_frequency/ambulance/frequency_to_referral_facility": "daily",
             "loop_over_transport_types_frequency/bicycle/frequency_to_referral_facility": "weekly"
             },
            {},
            {"available_transportation_types_to_referral_facility/ambulance":
             True,
             "loop_over_transport_types_frequency/ambulance/frequency_to_referral_facility": "weekly",
             },
            {"available_transportation_types_to_referral_facility/taxi": True,
             "available_transportation_types_to_referral_facility/other": True,
             "available_transportation_types_to_referral_facility_other":
             "camel",
             "loop_over_transport_types_frequency/taxi/frequency_to_referral_facility": "daily",
             "loop_over_transport_types_frequency/other/frequency_to_referral_facility": "other",
             }
        ]
        for d_from_db in self.data_dictionary.get_data_for_excel():
            for k, v in d_from_db.items():
                if (k != u'_xform_id_string' and k != 'meta/instanceID') and v:
                    new_key = k[len('transport/'):]
                    d_from_db[new_key] = d_from_db[k]
                del d_from_db[k]
            self.assertTrue(d_from_db in data)
            data.remove(d_from_db)
        self.assertEquals(data, [])

    def _check_group_xpaths_do_not_appear_in_dicts_for_export(self):
        # todo: not sure which order the instances are getting put
        # into the database, the hard coded index below should be
        # fixed.
        instance = self.xform.surveys.all()[1]
        expected_dict = {
            u"transportation": {
                u"meta": {u"instanceID": u"uuid:f3d8dc65-91a6-4d0f-9e97-802128083390"},
                u"transport": {
                    u"loop_over_transport_types_frequency": {u"bicycle": {
                        u"frequency_to_referral_facility": u"weekly"
                    },
                    u"ambulance": {
                        u"frequency_to_referral_facility": u"daily"
                    }},
                    u"available_transportation_types_to_referral_facility":
                    u"ambulance bicycle",
                }
            }
        }
        self.assertEqual(instance.get_dict(flat=False), expected_dict)
        expected_dict = {
            u"transport/available_transportation_types_to_referral_facility":
            u"ambulance bicycle",
            u"transport/loop_over_transport_types_frequency/ambulance/frequency_to_referral_facility": u"daily",
            u"transport/loop_over_transport_types_frequency/bicycle/frequency_to_referral_facility": u"weekly",
            u"_xform_id_string": u"transportation_2011_07_25",
            u"meta/instanceID": u"uuid:f3d8dc65-91a6-4d0f-9e97-802128083390"
        }
        self.assertEqual(instance.get_dict(), expected_dict)

    def _get_csv_(self):
        # todo: get the csv.reader to handle unicode as done here:
        # http://docs.python.org/library/csv.html#examples
        url = reverse(csv_export, kwargs={
            'username': self.user.username, 'id_string': self.xform.id_string})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        actual_csv = response.content
        actual_lines = actual_csv.split("\n")
        return csv.reader(actual_lines)

    def _check_csv_export_first_pass(self):
        actual_csv = self._get_csv_()
        f = open(os.path.join(
            self.this_directory, "fixtures",
            "transportation", "transportation.csv"), "r")
        expected_csv = csv.reader(f)
        for actual_row, expected_row in zip(actual_csv, expected_csv):
            for actual_cell, expected_cell in zip(actual_row, expected_row):
                self.assertEqual(actual_cell, expected_cell)
        f.close()

    def _check_csv_export_second_pass(self):
        url = reverse(csv_export, kwargs={
            'username': self.user.username, 'id_string': self.xform.id_string})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        actual_csv = response.content
        actual_lines = actual_csv.split("\n")
        actual_csv = csv.reader(actual_lines)
        headers = actual_csv.next()
        data = [
            {'meta/instanceID': 'uuid:5b2cc313-fc09-437e-8149-fcd32f695d41'},
            {"available_transportation_types_to_referral_facility/ambulance":
             "True",
             "available_transportation_types_to_referral_facility/bicycle":
             "True",
             "loop_over_transport_types_frequency/ambulance/frequency_to_referral_facility": "daily",
             "loop_over_transport_types_frequency/bicycle/frequency_to_referral_facility": "weekly",
             "meta/instanceID": "uuid:f3d8dc65-91a6-4d0f-9e97-802128083390"
             },
            {"available_transportation_types_to_referral_facility/ambulance":
             "True",
             "loop_over_transport_types_frequency/ambulance/frequency_to_referral_facility": "weekly",
             "meta/instanceID": "uuid:9c6f3468-cfda-46e8-84c1-75458e72805d"
             },
            {"available_transportation_types_to_referral_facility/taxi":
             "True",
             "available_transportation_types_to_referral_facility/other":
             "True",
             "available_transportation_types_to_referral_facility_other":
             "camel",
             "loop_over_transport_types_frequency/taxi/frequency_to_referral_facility": "daily",
             "meta/instanceID": "uuid:9f0a1508-c3b7-4c99-be00-9b237c26bcbf"
             }
        ]

        dd = DataDictionary.objects.get(pk=self.xform.pk)
        for row, expected_dict in zip(actual_csv, data):
            d = dict(zip(headers, row))
            for k, v in d.items():
                if v in ["n/a", "False"] or k in dd._additional_headers():
                    del d[k]
            l =  []
            for k, v in expected_dict.items():
                if k == 'meta/instanceID':
                    l.append((k, v))
                else:
                    l.append(("transport/" + k, v))
            self.assertEqual(d, dict(l))

    def _check_delete(self):
        self.assertEquals(self.user.xforms.count(), 1)
        self.user.xforms.all()[0].delete()
        self.assertEquals(self.user.xforms.count(), 0)

    def test_405_submission(self):
        url = reverse(submission)
        response = self.client.get(url)
        self.assertContains(
            response, "405 Error: Method Not Allowed", status_code=405)

    def test_publish_bad_xls_with_unicode_in_error(self):
        """
        Check that publishing a bad xls where the error has a unicode character
        returns a 200, thus showing a readable error to the user
        """
        self._create_user_and_login()
        path = os.path.join(
            self.this_directory, 'fixtures',
            'form_with_unicode_in_relevant_column.xlsx')
        response = MainTestCase._publish_xls_file(self, path)
        # make sure we get a 200 response
        self.assertEqual(response.status_code, 200)
