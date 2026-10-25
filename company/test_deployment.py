import importlib.util
import json
from pathlib import Path
import unittest


def module(name):
    spec=importlib.util.spec_from_file_location('company_'+name,Path(__file__).with_name(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


class DeploymentContracts(unittest.TestCase):
    def test_portable_loopback_services_and_explicit_lan_edge(self):
        self.assertTrue(Path(__file__).with_name('render.py').exists(),'Linux deployment renderer missing')
        site=module('site').Site('company','Company','https://10.20.30.40:9443','10.20.30.40',['10.20.30.0/24'],'admin@example.invalid')
        rendered=module('render').render(site,{'database':25432,'gateway':28400,'portal':28401},'internal')
        text=json.dumps(rendered)
        self.assertNotIn('192.168.178.65',text)
        self.assertNotIn('owner@minipc.invalid',text)
        services=rendered['compose']['services']
        self.assertIn('127.0.0.1',services['proxy']['command'])
        self.assertEqual(services['portal']['environment']['MINIPC_PORTAL_STATE'],'/state')
        self.assertNotIn('proxy.env',str(services['portal']))
        self.assertEqual(services['proxy']['environment']['STORE_MODEL_IN_DB'],'True')
        self.assertIn('bind 10.20.30.40',rendered['caddy'])
        self.assertIn('10.20.30.0/24',rendered['caddy'])
        self.assertIn('handle /connect/api/*',rendered['caddy'])
        self.assertEqual(rendered['config']['model_list'],[])

    def test_port_collisions_and_bad_tls_are_rejected(self):
        self.assertTrue(Path(__file__).with_name('render.py').exists())
        site=module('site').Site('company','Company','https://10.20.30.40:9443','10.20.30.40',['10.20.30.0/24'],'admin@example.invalid')
        for ports,tls in [({'database':18400,'gateway':18400,'portal':18401},'internal'),({'database':15432,'gateway':18400,'portal':18401},'disabled')]:
            with self.assertRaises(ValueError):module('render').render(site,ports,tls)


if __name__=='__main__':unittest.main()
