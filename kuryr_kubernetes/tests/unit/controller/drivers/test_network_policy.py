# Copyright 2018 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import mock

from kuryr_kubernetes.controller.drivers import network_policy
from kuryr_kubernetes import exceptions
from kuryr_kubernetes.tests import base as test_base
from kuryr_kubernetes.tests.unit import kuryr_fixtures as k_fix

from neutronclient.common import exceptions as n_exc


class TestNetworkPolicyDriver(test_base.TestCase):

    def setUp(self):
        super(TestNetworkPolicyDriver, self).setUp()
        self._project_id = mock.sentinel.project_id
        self._policy_name = 'np-test'
        self._policy_uid = mock.sentinel.policy_uid
        self._policy_link = mock.sentinel.policy_link
        self._sg_id = mock.sentinel.sg_id
        self._i_rules = [{'security_group_rule': {'id': ''}}]
        self._e_rules = [{'security_group_rule': {'id': ''}}]

        self._policy = {
            'apiVersion': u'networking.k8s.io/v1',
            'kind': u'NetworkPolicy',
            'metadata': {
                'name': self._policy_name,
                'resourceVersion': u'2259309',
                'generation': 1,
                'creationTimestamp': u'2018-09-18T14:09:51Z',
                'namespace': u'default',
                'annotations': {},
                'selfLink': self._policy_link,
                'uid': self._policy_uid
            },
            'spec': {
                'egress': [{'ports':
                            [{'port': 5978, 'protocol': 'TCP'}]}],
                'ingress': [{'ports':
                             [{'port': 6379, 'protocol': 'TCP'}]}],
                'policyTypes': ['Ingress', 'Egress']
            }
        }

        self._crd = {
            'metadata': {'name': mock.sentinel.name,
                         'selfLink': mock.sentinel.selfLink},
            'spec': {
                'egressSgRules': [
                    {'security_group_rule':
                     {'description': 'Kuryr-Kubernetes NetPolicy SG rule',
                      'direction': 'egress',
                      'ethertype': 'IPv4',
                      'port_range_max': 5978,
                      'port_range_min': 5978,
                      'protocol': 'tcp',
                      'security_group_id': self._sg_id,
                      'id': mock.sentinel.id
                      }}],
                'ingressSgRules': [
                    {'security_group_rule':
                     {'description': 'Kuryr-Kubernetes NetPolicy SG rule',
                      'direction': 'ingress',
                      'ethertype': 'IPv4',
                      'port_range_max': 6379,
                      'port_range_min': 6379,
                      'protocol': 'tcp',
                      'security_group_id': self._sg_id,
                      'id': mock.sentinel.id
                      }}],
                'securityGroupId': self._sg_id,
                'securityGroupName': mock.sentinel.sg_name}}

        self.neutron = self.useFixture(k_fix.MockNeutronClient()).client
        self.kubernetes = self.useFixture(k_fix.MockK8sClient()).client
        self._driver = network_policy.NetworkPolicyDriver()

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_get_kuryrnetpolicy_crd', return_value=False)
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'create_security_group_rules_from_network_policy')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'update_security_group_rules_from_network_policy')
    def test_ensure_network_policy(self, m_update, m_create, m_get_crd):
        self._driver.ensure_network_policy(self._policy, self._project_id)

        m_get_crd.assert_called_once_with(self._policy)
        m_create.assert_called_once_with(self._policy, self._project_id)
        m_update.assert_not_called()

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_get_kuryrnetpolicy_crd', return_value=True)
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'create_security_group_rules_from_network_policy')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'update_security_group_rules_from_network_policy')
    def test_ensure_network_policy_with_existing_crd(self, m_update, m_create,
                                                     m_get_crd):
        self._driver.ensure_network_policy(self._policy, self._project_id)

        m_get_crd.assert_called_once_with(self._policy)
        m_create.assert_not_called()
        m_update.assert_called_once_with(self._policy)

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_get_kuryrnetpolicy_crd')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_add_kuryrnetpolicy_crd')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'parse_network_policy_rules')
    def test_create_security_group_rules_from_network_policy(self, m_parse,
                                                             m_add_crd,
                                                             m_get_crd):
        self._driver.neutron.create_security_group.return_value = {
            'security_group': {'id': mock.sentinel.id}}
        m_parse.return_value = (self._i_rules, self._e_rules)
        self._driver.neutron.create_security_group_rule.return_value = {
            'security_group_rule': {'id': mock.sentinel.id}}
        self._driver.create_security_group_rules_from_network_policy(
            self._policy, self._project_id)
        m_get_crd.assert_called_once()
        m_add_crd.assert_called_once()

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_get_kuryrnetpolicy_crd')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_add_kuryrnetpolicy_crd')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'parse_network_policy_rules')
    def test_create_security_group_rules_with_k8s_exc(self, m_parse,
                                                      m_add_crd, m_get_crd):
        self._driver.neutron.create_security_group.return_value = {
            'security_group': {'id': mock.sentinel.id}}
        m_parse.return_value = (self._i_rules, self._e_rules)
        m_get_crd.side_effect = exceptions.K8sClientException
        self._driver.neutron.create_security_group_rule.return_value = {
            'security_group_rule': {'id': mock.sentinel.id}}
        self.assertRaises(
            exceptions.K8sClientException,
            self._driver.create_security_group_rules_from_network_policy,
            self._policy, self._project_id)
        m_add_crd.assert_called_once()

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_get_kuryrnetpolicy_crd')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_add_kuryrnetpolicy_crd')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'parse_network_policy_rules')
    def test_create_security_group_rules_error_add_crd(self, m_parse,
                                                       m_add_crd, m_get_crd):
        self._driver.neutron.create_security_group.return_value = {
            'security_group': {'id': mock.sentinel.id}}
        m_parse.return_value = (self._i_rules, self._e_rules)
        m_add_crd.side_effect = exceptions.K8sClientException
        self._driver.neutron.create_security_group_rule.return_value = {
            'security_group_rule': {'id': mock.sentinel.id}}
        self.assertRaises(
            exceptions.K8sClientException,
            self._driver.create_security_group_rules_from_network_policy,
            self._policy, self._project_id)
        m_get_crd.assert_not_called()

    def test_create_security_group_rules_with_n_exc(self):
        self._driver.neutron.create_security_group.side_effect = (
            n_exc.NeutronClientException())
        self.assertRaises(
            n_exc.NeutronClientException,
            self._driver.create_security_group_rules_from_network_policy,
            self._policy, self._project_id)

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_create_security_group_rule')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_get_kuryrnetpolicy_crd')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'parse_network_policy_rules')
    def test_update_security_group_rules(self, m_parse, m_get_crd,
                                         m_create_sgr):
        m_get_crd.return_value = self._crd
        m_parse.return_value = (self._i_rules, self._e_rules)
        self._driver.update_security_group_rules_from_network_policy(
            self._policy)
        m_parse.assert_called_with(self._policy, self._sg_id)

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_create_security_group_rule')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_get_kuryrnetpolicy_crd')
    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       'parse_network_policy_rules')
    def test_update_security_group_rules_with_k8s_exc(self, m_parse, m_get_crd,
                                                      m_create_sgr):
        self._driver.kubernetes.patch.side_effect = (
            exceptions.K8sClientException())
        m_get_crd.return_value = self._crd
        m_parse.return_value = (self._i_rules, self._e_rules)
        self.assertRaises(
            exceptions.K8sClientException,
            self._driver.update_security_group_rules_from_network_policy,
            self._policy)
        m_parse.assert_called_with(self._policy, self._sg_id)

    def test_parse_network_policy_rules(self):
        i_rule, e_rule = (
            self._driver.parse_network_policy_rules(self._policy, self._sg_id))
        self.assertEqual(
            self._policy['spec']['ingress'][0]['ports'][0]['port'],
            i_rule[0]['security_group_rule']['port_range_min'])
        self.assertEqual(
            self._policy['spec']['egress'][0]['ports'][0]['port'],
            e_rule[0]['security_group_rule']['port_range_min'])

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_create_security_group_rule_body')
    def test_parse_network_policy_rules_with_rules(self, m_create):
        self._driver.parse_network_policy_rules(self._policy, self._sg_id)
        m_create.assert_called()

    @mock.patch.object(network_policy.NetworkPolicyDriver,
                       '_create_security_group_rule_body')
    def test_parse_network_policy_rules_with_no_rules(self, m_create):
        self._policy['spec'] = {}
        self._driver.parse_network_policy_rules(self._policy, self._sg_id)
        m_create.assert_not_called()