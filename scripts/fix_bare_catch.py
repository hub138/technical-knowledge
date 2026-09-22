# 补 shell.js 与 i18n.js 的裸 catch 参数：可选绑定参数是 2019 年语法，
# 旧手机 WebView 不支持。逐处精确替换，计数先行。
PATHS = [
    "site/shell.js",
    "site/i18n.js",
]

REPLACEMENTS = {
    "site/shell.js": [
        ("    } catch {\n      return null;\n    }\n  })();",
         "    } catch (err) {\n      return null;\n    }\n  })();"),
        ("      return localStorage.getItem(THEME_KEY);\n    } catch {\n      return null;\n    }",
         "      return localStorage.getItem(THEME_KEY);\n    } catch (err) {\n      return null;\n    }"),
        ("      localStorage.setItem(THEME_KEY, next);\n    } catch {\n      /* private mode — the choice just will not persist */\n    }",
         "      localStorage.setItem(THEME_KEY, next);\n    } catch (err) {\n      /* private mode — the choice just will not persist */\n    }"),
        ("      const saved = localStorage.getItem(FB_NAME_KEY);\n      if (saved) name.value = saved;\n    } catch {",
         "      const saved = localStorage.getItem(FB_NAME_KEY);\n      if (saved) name.value = saved;\n    } catch (err) {"),
        ("        try {\n          localStorage.setItem(FB_NAME_KEY, name.value.trim());\n        } catch {",
         "        try {\n          localStorage.setItem(FB_NAME_KEY, name.value.trim());\n        } catch (err) {"),
        ("        if (moved) this.save();\n      } catch {\n        this.data = { learned: {}, planned: {} };\n      }",
         "        if (moved) this.save();\n      } catch (err) {\n        this.data = { learned: {}, planned: {} };\n      }"),
        ("      try { localStorage.setItem(this.KEY, JSON.stringify(this.data)); }\n      catch { /* 存储满/隐私模式：进度丢就丢，不影响阅读 */ }",
         "      try { localStorage.setItem(this.KEY, JSON.stringify(this.data)); }\n      catch (err) { /* 存储满/隐私模式：进度丢就丢，不影响阅读 */ }"),
    ],
    "site/i18n.js": [],
}

for path in PATHS:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    for old, new in REPLACEMENTS[path]:
        n = text.count(old)
        print(path, "count=", n, repr(old[:60]))
        text = text.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
print("done")
