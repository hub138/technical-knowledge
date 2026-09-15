(() => {
  const cardByName = (name) =>
    [...document.querySelectorAll(".project")].find(
      (card) => card.querySelector("h3")?.textContent.trim() === name,
    );

  document.addEventListener("DOMContentLoaded", () => {
    const openmaic = cardByName("OpenMAIC");
    const deeptutor = cardByName("DeepTutor");
    for (const card of [openmaic, deeptutor]) {
      if (!card) continue;
      const launch = card.querySelector("[data-service-port]");
      if (!launch) continue;
      launch.target = "_blank";
      launch.rel = "noopener noreferrer";
    }
    if (openmaic) openmaic.id = "openmaic";
    if (deeptutor) deeptutor.id = "deeptutor";
  });
})();
