#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock
from oslo_config import cfg
from oslo_utils import importutils

from cinder import context
from cinder import db
from cinder import exception
from cinder.objects import fields
from cinder import test
from cinder.tests.unit import fake_constants as fake
from cinder.tests.unit import utils as tests_utils
from cinder.volume import configuration as conf

CONF = cfg.CONF


class AttachmentManagerTestCase(test.TestCase):
    """Attachment related test for volume.manager.py."""

    def setUp(self):
        """Setup test class."""
        super(AttachmentManagerTestCase, self).setUp()
        self.manager = importutils.import_object(CONF.volume_manager)
        self.configuration = mock.Mock(conf.Configuration)
        self.context = context.get_admin_context()
        self.context.user_id = fake.USER_ID
        self.project_id = fake.PROJECT3_ID
        self.context.project_id = self.project_id
        self.manager.driver.set_initialized()
        self.manager.stats = {'allocated_capacity_gb': 100,
                              'pools': {}}

    @mock.patch.object(db, 'volume_admin_metadata_update')
    @mock.patch('cinder.message.api.API.create', mock.Mock())
    def test_attachment_update_with_readonly_volume(self, mock_update):
        mock_update.return_value = {'readonly': 'True'}
        vref = tests_utils.create_volume(self.context, **{'status':
                                                          'available'})
        self.manager.create_volume(self.context, vref)
        attachment_ref = db.volume_attach(self.context,
                                          {'volume_id': vref.id,
                                           'volume_host': vref.host,
                                           'attach_status': 'reserved',
                                           'instance_uuid': fake.UUID1})

        with mock.patch.object(self.manager,
                               '_notify_about_volume_usage',
                               return_value=None), mock.patch.object(
                self.manager, '_connection_create'):
            self.assertRaises(exception.InvalidVolumeAttachMode,
                              self.manager.attachment_update,
                              self.context, vref, {}, attachment_ref.id)
            attachment = db.volume_attachment_get(self.context,
                                                  attachment_ref.id)
            self.assertEqual(fields.VolumeAttachStatus.ERROR_ATTACHING,
                             attachment['attach_status'])

    def test_attachment_update(self):
        """Test attachment_update."""
        volume_params = {'status': 'available'}
        connector = {
            "initiator": "iqn.1993-08.org.debian:01:cad181614cec",
            "ip": "192.168.1.20",
            "platform": "x86_64",
            "host": "tempest-1",
            "os_type": "linux2",
            "multipath": False}

        vref = tests_utils.create_volume(self.context, **volume_params)
        self.manager.create_volume(self.context, vref)
        values = {'volume_id': vref.id,
                  'attached_host': vref.host,
                  'attach_status': 'reserved',
                  'instance_uuid': fake.UUID1}
        attachment_ref = db.volume_attach(self.context, values)
        with mock.patch.object(
                self.manager, '_notify_about_volume_usage',
                return_value=None), mock.patch.object(
                self.manager.driver, 'attach_volume') as mock_driver:
            expected = {
                'encrypted': False,
                'qos_specs': None,
                'access_mode': 'rw',
                'driver_volume_type': 'iscsi',
                'attachment_id': attachment_ref.id}

            self.assertEqual(expected,
                             self.manager.attachment_update(
                                 self.context,
                                 vref,
                                 connector,
                                 attachment_ref.id))
            mock_driver.assert_called_once_with(self.context,
                                                vref,
                                                attachment_ref.instance_uuid,
                                                "tempest-1",
                                                "na")
            new_attachment_ref = db.volume_attachment_get(self.context,
                                                          attachment_ref.id)
            for attr, expected in (('instance_uuid',
                                    attachment_ref.instance_uuid),
                                   ('attached_host', connector['host']),
                                   ('mountpoint', 'na'),
                                   ('attach_mode', 'rw')):
                self.assertEqual(expected, new_attachment_ref[attr])
            new_volume_ref = db.volume_get(self.context,
                                           vref.id)
            self.assertEqual('in-use', new_volume_ref['status'])
            self.assertEqual(fields.VolumeAttachStatus.ATTACHED,
                             new_volume_ref['attach_status'])

    def test_attachment_delete(self):
        """Test attachment_delete."""
        volume_params = {'status': 'available'}

        vref = tests_utils.create_volume(self.context, **volume_params)
        self.manager.create_volume(self.context, vref)
        values = {'volume_id': vref.id,
                  'volume_host': vref.host,
                  'attach_status': 'reserved',
                  'instance_uuid': fake.UUID1}
        attachment_ref = db.volume_attach(self.context, values)
        attachment_ref = db.volume_attachment_get(
            self.context,
            attachment_ref['id'])
        self.manager.attachment_delete(self.context,
                                       attachment_ref['id'],
                                       vref)
        self.assertRaises(exception.VolumeAttachmentNotFound,
                          db.volume_attachment_get,
                          self.context,
                          attachment_ref.id)
