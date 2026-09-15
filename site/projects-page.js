(() => {
  document.addEventListener("DOMContentLoaded", () => {
    const hero = document.querySelector(".hero-links");
    if (hero && !hero.querySelector('a[href="/learn"]')) {
      const learn = document.createElement("a");
      learn.className = "primary";
      learn.href = "/learn";
      learn.target = "_blank";
      learn.rel = "noopener noreferrer";
      learn.textContent = "打开学习中心";
      hero.prepend(learn);
    }
    const copy = document.querySelector("#access-copy");
    fetch("/api/access", { cache: "no-store" })
      .then((response) => response.json())
      .then((access) => {
        if (!copy) return;
        copy.textContent = access.local_client
          ? "当前是本机访问：知识库公开可读，启动教学工具自动使用已配置凭据。"
          : "当前是其他设备访问：知识库公开可读；启动教学工具前需要输入访问密码。";
      })
      .catch(() => {
        if (copy)
          copy.textContent =
            "访问状态暂时无法确认；知识库仍可阅读，启动教学工具时会按需要求授权。";
      });
  });
})();
