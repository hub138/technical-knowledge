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

    def test_all_engineering_articles_preserve_structure(self):
        parser = SERVER_MODULE.MarkdownIt('commonmark', {'html': False}).enable('table')
        checked = 0
        for path in self.vault.notes:
            if not path.startswith('工程知识/'):
                continue
            with self.subTest(path=path):
                note = self.vault.note(path)
                tokens = parser.parse(note['body'])
                document = self.render(path)
                headings = document.select('h1,h2,h3,h4,h5,h6')
                ids = [heading['id'] for heading in headings]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(len(headings), sum(token.type == 'heading_open' for token in tokens))
                self.assertEqual(len(document.select('li')), sum(token.type == 'list_item_open' for token in tokens))
                self.assertEqual(len(document.select('table')), sum(token.type == 'table_open' for token in tokens))
                depth, expected_depths = 0, []
                for token in tokens:
                    if token.type in ('bullet_list_open', 'ordered_list_open'):
                        depth += 1
                    elif token.type in ('bullet_list_close', 'ordered_list_close'):
                        depth -= 1
                    elif token.type == 'list_item_open':
                        expected_depths.append(depth)
                actual_depths = [len(node.find_parents(['ul', 'ol'])) for node in document.select('li')]
                self.assertEqual(actual_depths, expected_depths)
                expected_starts = [int(token.attrGet('start') or 1) for token in tokens if token.type == 'ordered_list_open']
                self.assertEqual([int(node.get('start', 1)) for node in document.select('ol')], expected_starts)
                self.assertEqual(len(document.select('blockquote,aside.callout')), sum(token.type == 'blockquote_open' for token in tokens))
                expected_code = [token.content.removesuffix('\n') for token in tokens
                                 if token.type in ('fence', 'code_block')
                                 and token.info.split()[:1] != ['mermaid']]
                self.assertEqual([node.get_text() for node in document.select('.code-block > code')], expected_code)
                self.assertEqual(document.select('script,[onclick],[onload],[onerror]'), [])
                checked += 1
        self.assertGreater(checked, 400)

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
