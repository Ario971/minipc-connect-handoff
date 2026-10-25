import importlib.util
import unittest
from pathlib import Path


class SiteContracts(unittest.TestCase):
    def test_portable_site_contracts(self):
        path = Path(__file__).with_name('site.py')
        self.assertTrue(path.exists(), 'Portable site configuration has not been implemented')
        spec = importlib.util.spec_from_file_location('minipc_site', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        site = module.Site('company-pilot', 'Company MiniPC', 'https://10.20.30.40:9443',
                           '10.20.30.40', ['10.20.30.0/24'], 'admin@example.invalid', 8192, 1024)
        self.assertEqual(site.origin, 'https://10.20.30.40:9443')
        self.assertEqual(site.model_alias, 'local-coder')
        for changes in ({'origin': 'http://10.20.30.40:9443'},
                        {'origin': 'https://password@example.invalid'},
                        {'origin': 'https://10.20.30.40:9443/path'},
                        {'networks': ['0.0.0.0/0']}, {'networks': []},
                        {'site_id': '../secrets'}, {'output': 9000}):
            values = dict(site_id='company-pilot', name='Company MiniPC', origin='https://10.20.30.40:9443',
                          bind='10.20.30.40', networks=['10.20.30.0/24'], email='admin@example.invalid',
                          context=8192, output=1024)
            values.update(changes)
            with self.assertRaises(ValueError):
                module.Site(**values)
        public = site.public_info()
        self.assertNotIn('email', public)
        self.assertNotIn('api_key', public)
        self.assertNotIn('192.168.178.65', str(public))

    def test_discovery_is_explicit_and_bounded(self):
        path = Path(__file__).with_name('discovery.py')
        self.assertTrue(path.exists(), 'Explicit model discovery has not been implemented')
        spec = importlib.util.spec_from_file_location('minipc_discovery', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.models_url('http://127.0.0.1:11434/v1'), 'http://127.0.0.1:11434/v1/models')
        self.assertEqual(module.models_url('http://127.0.0.1:11434'), 'http://127.0.0.1:11434/v1/models')
        for value in ('http://169.254.169.254/', 'http://user:pass@127.0.0.1:8000',
                      'file:///etc/passwd', 'http://127.0.0.1:8000/?api_key=secret'):
            with self.assertRaises(ValueError):
                module.models_url(value)
        self.assertEqual(module.parse_models({'data': [{'id': 'company-model'}, {'id': 'company-model'}]}), ['company-model'])
        with self.assertRaises(ValueError):
            module.parse_models({'data': [{'id': 'a'}] * 257})
        with self.assertRaises(ValueError):
            module.parse_models({'error': 'not a model list'})


if __name__ == '__main__':
    unittest.main()
