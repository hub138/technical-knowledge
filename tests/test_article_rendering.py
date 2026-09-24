import unittest

from bs4 import BeautifulSoup

from tests.test_site import ROOT, SERVER_MODULE


LIST_NOTE = "工程知识/AI 系统工程：从模型能力到生产能力/Agent与工作流/任务分解的质量决定Agent的上限.md"
REPEATED_NOTE = "工程知识/缺陷分析：从个案到体系/安全/案例四十四：投毒不是写错，是写给你看——依赖投毒的三个真实剧本.md"


class ArticleRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vault = SERVER_MODULE.Vault(ROOT / "vault")

    def render(self, path):
        note = self.vault.note(path)
        self.assertIsNotNone(note, path)
        return BeautifulSoup(SERVER_MODULE.render_markdown(note["body"], self.vault, path), "html.parser")

    def test_nested_list_preserves_parent(self):
        document = self.render(LIST_NOTE)
        label = next(node for node in document.select('li > strong') if node.get_text() == '可并行')
        parent = label.parent.find_parent('li')
        self.assertIsNotNone(parent, '可并行应位于可恢复的子列表')
        self.assertEqual(parent.find('strong', recursive=False).get_text(), '可恢复')
        self.assertIsNotNone(label.parent.find('a', attrs={'data-note': True}), '子列表中的站内链接必须可用')

    def test_repeated_headings_have_distinct_ids(self):
        document = self.render(REPEATED_NOTE)
        headings = [node for node in document.select('h3') if node.get_text() == '机制']
        self.assertEqual(len(headings), 3)
        self.assertEqual(len({node['id'] for node in headings}), 3)
        self.assertEqual(headings[0]['id'], '机制')

    def test_real_article_tables_and_code_remain_structured(self):
        document = self.render(LIST_NOTE)
        self.assertGreater(len(document.select('.code-block > code')), 0)
        for table in document.select('table'):
            self.assertIn('table-wrap', table.parent.get('class', []))
            columns = len(table.select('thead th'))
            self.assertGreater(columns, 0)
            for row in table.select('tbody tr'):
                self.assertEqual(len(row.find_all('td', recursive=False)), columns)
        self.assertEqual(document.select('script,[onclick],[onload],[onerror]'), [])


if __name__ == '__main__':
    unittest.main()
