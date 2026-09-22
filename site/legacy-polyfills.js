/* 老旧 WebView 兼容补丁。加载顺序：必须在所有站点脚本之前执行。
 *
 * 覆盖对象：公司内旧款安卓（微信 X5、企业微信内置浏览器、Chromium 61-79
 * 区间的系统 WebView）。站点此前已把语法层（?.、??）降级到 2017 标准，
 * 这里补的是运行时函数缺失 —— 缺一个就抛引用错误，整段脚本作废。
 */
(function () {
  "use strict";

  /* String.prototype.replaceAll —— Chromium 85+ */
  if (!String.prototype.replaceAll) {
    Object.defineProperty(String.prototype, "replaceAll", {
      configurable: true,
      writable: true,
      value: function (search, replacement) {
        if (search instanceof RegExp) {
          if (!search.global) {
            throw new TypeError("replaceAll must be called with a global RegExp");
          }
          return this.replace(search, replacement);
        }
        return this.split(search).join(replacement);
      },
    });
  }

  /* Array.prototype.at —— Chromium 92+。负索引从尾部计数。 */
  if (!Array.prototype.at) {
    Object.defineProperty(Array.prototype, "at", {
      configurable: true,
      writable: true,
      value: function (index) {
        var n = Math.trunc(Number(index) || 0);
        if (n < 0) n += this.length;
        if (n < 0 || n >= this.length) return undefined;
        return this[n];
      },
    });
  }

  /* Object.fromEntries —— Chromium 73+ */
  if (typeof Object.fromEntries !== "function") {
    Object.defineProperty(Object, "fromEntries", {
      configurable: true,
      writable: true,
      value: function (entries) {
        var out = {};
        Array.prototype.forEach.call(entries, function (pair) {
          out[pair[0]] = pair[1];
        });
        return out;
      },
    });
  }

  /* structuredClone —— Chromium 98+。深拷贝走 JSON 路线，函数与
     undefined 会被丢弃，站点数据全是纯 JSON，足够。 */
  if (typeof window.structuredClone !== "function") {
    window.structuredClone = function (value) {
      return JSON.parse(JSON.stringify(value));
    };
  }

  /* flatMap / flat —— Chromium 69+，edge case 上仍补齐 */
  if (!Array.prototype.flatMap) {
    Object.defineProperty(Array.prototype, "flatMap", {
      configurable: true,
      writable: true,
      value: function (fn) {
        return Array.prototype.concat.apply([], this.map(fn));
      },
    });
  }
  if (!Array.prototype.flat) {
    Object.defineProperty(Array.prototype, "flat", {
      configurable: true,
      writable: true,
      value: function (depth) {
        var d = depth === undefined ? 1 : Math.floor(Number(depth) || 0);
        var out = [];
        var walk = function (arr) {
          Array.prototype.forEach.call(arr, function (item) {
            if (Array.isArray(item) && d > 0) {
              d -= 1;
              walk(item);
              d += 1;
            } else {
              out.push(item);
            }
          });
        };
        walk(this);
        return out;
      },
    });
  }
})();
