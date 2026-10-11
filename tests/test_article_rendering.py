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
        # 用固定文本渲染，不读真实笔记：那篇「案例四十四」会被定时 patrol
        # 自动改写（2026-09-27 18:17 就把三个「### 机制」改没了），测试一依赖
        # 真实文件就会被自动流程打红 —— 它该测的是"重复标题 id 是否有 distinct
        # 后缀"，不是某篇笔记此刻长什么样。
        body = (
            "### 机制\n第一种。\n\n"
            "### 机制\n第二种。\n\n"
            "### 机制\n第三种。\n"
        )
        document = BeautifulSoup(
            SERVER_MODULE.render_markdown(body, self.vault, 'defect/case.md'), 'html.parser')
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

    def test_emphasis_preserves_sql_wildcard(self):
        document = self.render('工程知识/数据系统：在并发与故障中保存事实/查询与索引/列存与向量化执行：OLAP引擎快的两个来源.md')
        self.assertIn('SELECT * 是列存的反模式', [node.get_text() for node in document.select('strong')])

    def test_real_inline_code_preserves_literal_markdown(self):
        parser = SERVER_MODULE.MarkdownIt('commonmark', {'html': False}).enable('table')
        checked = 0
        for path in self.vault.notes:
            if not path.startswith('工程知识/'):
                continue
            note = self.vault.note(path)
            for block in parser.parse(note['body']):
                if block.type != 'inline' or not block.children:
                    continue
                expected = [token.content for token in block.children if token.type == 'code_inline']
                if not expected:
                    continue
                with self.subTest(path=path, source=block.content[:60]):
                    rendered = SERVER_MODULE.render_inline(block.content, self.vault, path)
                    document = BeautifulSoup(rendered, 'html.parser')
                    self.assertEqual([node.get_text() for node in document.select('code')], expected)
                    self.assertEqual(document.select('code a,code img,code strong,code em'), [])
                    checked += 1
        self.assertGreater(checked, 100)

    def test_real_inline_emphasis_matches_commonmark(self):
        parser = SERVER_MODULE.MarkdownIt('commonmark', {'html': False}).enable('table')
        checked = 0
        for path in self.vault.notes:
            if not path.startswith('工程知识/'):
                continue
            for block in parser.parse(self.vault.note(path)['body']):
                if block.type != 'inline' or '[[' in block.content or '<iframe' in block.content:
                    continue
                expected = BeautifulSoup(parser.renderInline(block.content), 'html.parser')
                actual = BeautifulSoup(SERVER_MODULE.render_inline(block.content, self.vault, path), 'html.parser')
                with self.subTest(path=path, source=block.content[:60]):
                    for tag in ('strong', 'em'):
                        self.assertEqual([node.get_text() for node in actual.select(tag)],
                                         [node.get_text() for node in expected.select(tag)])
                    for link in actual.select('a[target="_blank"]'):
                        self.assertIn('noopener', link.get('rel', []))
                        self.assertIn('noreferrer', link.get('rel', []))
                    checked += 1
        self.assertGreater(checked, 1000)

    def test_clipped_video_keeps_only_allowed_attributes(self):
        document = self.render('Clippings/自学两个月Agent，复盘思考.md')
        frames = document.select('.video-embed iframe')
        self.assertEqual(len(frames), 1)
        self.assertTrue(frames[0]['src'].startswith('https://player.bilibili.com/'))
        self.assertEqual(set(frames[0].attrs), {'src', 'title', 'frameborder', 'allowfullscreen', 'loading'})

    def test_callout_keeps_custom_title_and_body(self):
        document = self.render('知识库管理/归档/来源/实践证据/AI研发迭代框架案例.md')
        callout = document.select_one('aside.callout.warning')
        self.assertIsNotNone(callout)
        title = callout.select_one('.callout-title')
        self.assertEqual(title.get_text(), '证据边界')
        self.assertEqual(len(callout.select('.callout-title')), 1)
        self.assertIn('这是项目时期的证据快照', callout.get_text())
        self.assertIn('已复现', [node.get_text() for node in callout.select('code')])

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
