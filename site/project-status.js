(() => {
  const cardByName = (name) =>
    [...document.querySelectorAll(".project")].find(
      (card) => ((card.querySelector("h3") || {}).textContent || "").trim() === name,
    );

  const setStatus = (card, text) => {
    const status = card && card.querySelector(".status");
    if (status) status.textContent = text;
  };

  document.addEventListener("DOMContentLoaded", async () => {
    const openmaic = cardByName("OpenMAIC");
    const deeptutor = cardByName("DeepTutor");
    try {
      const response = await fetch("/api/learning/status", { cache: "no-store" });
      if (!response.ok) throw new Error("status unavailable");
      const status = await response.json();
      const maic = status.openmaic || {};
      const tutor = status.deeptutor || {};
      setStatus(
        openmaic,
        maic.online && maic.llm
          ? "互动课堂可用"
          : maic.online
            ? "服务运行中，模型待确认"
            : "互动课堂未启动",
      );
      setStatus(deeptutor, tutor.online && tutor.llm ? "学习导师可用" : "学习导师需配置");
    } catch (error) {
      setStatus(openmaic, "状态未知");
      setStatus(deeptutor, "状态未知");
    }
  });
})();
