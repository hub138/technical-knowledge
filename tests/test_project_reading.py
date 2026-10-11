import http.client
import secrets
import threading
import unittest
from urllib.parse import unquote

from bs4 import BeautifulSoup

from tests.test_site import ROOT, SERVER_MODULE


class ProjectReadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        relative = 'DeepTutor/assets/README/README_CN.md'
        output = SERVER_MODULE.render_project_markdown_page(ROOT / 'projects' / relative, relative, 'DeepTutor 中文项目说明')
        cls.document = BeautifulSoup(output, 'html.parser')

    def test_relative_document_link_uses_source_directory(self):
        link = self.document.find('a', string='CONTAINERIZATION.md')
        self.assertIsNotNone(link)
        self.assertEqual(unquote(link['href']), '/projects/DeepTutor/CONTAINERIZATION.md')

    def test_local_logo_is_rendered_as_image(self):
        image = self.document.find('img', alt='DeepTutor 标志')
        self.assertIsNotNone(image)
        self.assertEqual(image['src'], '/projects/DeepTutor/assets/figs/logo/logo.png')
        self.assertEqual(image['height'], '56')

    def test_all_document_toc_fragments_have_targets(self):
        links = self.document.select('.doc-body a[href^="#"]')
        self.assertGreater(len(links), 4)
        for link in links:
            with self.subTest(link=link.get_text()):
                self.assertIsNotNone(self.document.find(id=unquote(link['href'][1:])))

    def test_html_emphasis_has_no_literal_tags(self):
        self.assertTrue(any('方式一' in node.get_text() for node in self.document.select('.doc-body strong')))
        for node in self.document.select('.doc-body p'):
            self.assertNotIn('<b>', node.get_text())
        self.assertEqual(self.document.select('img[src*="img.shields.io"],img[src*="trendshift.io"]'), [])
        self.assertIsNotNone(self.document.find('a', string='Python 3.11+'))

    def test_html_image_conversion_preserves_code(self):
        self.assertEqual(self.document.select('.doc-body script,.doc-body [onerror],.doc-body [onclick]'), [])
        self.assertIsNotNone(self.document.select_one('.doc-body .code-block code'))


class ProjectAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vault = SERVER_MODULE.Vault(ROOT / 'vault')
        cls.server = SERVER_MODULE.KnowledgeHTTPServer(
            ('127.0.0.1', 0), SERVER_MODULE.Handler, vault, secrets.token_urlsafe(24))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, path):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=20)
        connection.request('GET', path)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_png_matches_repository_asset(self):
        relative = 'DeepTutor/assets/figs/logo/logo.png'
        status, headers, content = self.request('/projects/' + relative)
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'image/png')
        self.assertEqual(content, (ROOT / 'projects' / relative).read_bytes())
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_svg_has_sandbox_policy(self):
        status, headers, content = self.request('/projects/DeepTutor/assets/figs/partners/pageindex-mark.svg')
        self.assertEqual(status, 200)
        self.assertIn('sandbox', headers['Content-Security-Policy'])
        self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
        self.assertNotIn("script-src 'self'", headers['Content-Security-Policy'])

    def test_source_hidden_files_and_traversal_are_not_served(self):
        for path in ('/projects/DeepTutor/pyproject.toml', '/projects/../site/server.py',
                     '/projects/%2e%2e/site/server.py', '/projects/DeepTutor/.git/config'):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_relative_target_opens_as_document(self):
        status, headers, content = self.request('/projects/DeepTutor/CONTAINERIZATION.md')
        self.assertEqual(status, 200)
        self.assertIn('text/html', headers['Content-Type'])
        self.assertIsNotNone(BeautifulSoup(content, 'html.parser').select_one('.doc-body h1'))


if __name__ == '__main__':
    unittest.main()
