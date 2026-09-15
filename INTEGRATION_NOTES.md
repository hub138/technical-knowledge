# 本地整合记录

本项目的 `projects/` 来源于本机已安装的四个开源项目：

| 项目 | 上游地址 | 纳入内容 |
| --- | --- | --- |
| Archify | https://github.com/tt-a1i/archify | 完整 Git 跟踪源码、Skill、schema、渲染器、测试、示例和许可证 |
| OpenMAIC | https://github.com/THU-MAIC/OpenMAIC | 完整 Git 跟踪源码、互动课堂、Agent runtime、Skill、测试和许可证 |
| DeepTutor | https://github.com/HKUDS/DeepTutor | 完整 Git 跟踪源码、CLI、Web、RAG/记忆/学习能力、测试和许可证 |
| Matt Skills | https://github.com/mattpocock/skills | 完整 Skill、插件清单、文档和许可证 |

本机为了让工具能够从知识库首页带入主题，保留了两个未提交到上游的整合补丁：

- OpenMAIC 首页支持 `?topic=`，把知识库选中的主题带入课堂输入框。
- DeepTutor Chat 支持 `?prompt=`，把知识库选中的主题带入聊天输入框。

模型地址、API 密钥、访问码、登录账户和本机运行数据库不属于项目源码，不复制进仓库。网站与学习工具使用的秘密仍保存在本机 Keychain/运行目录中。
