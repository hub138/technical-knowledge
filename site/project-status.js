(() => {
  const cardByName = name => [...document.querySelectorAll('.project')].find(
    card => card.querySelector('h3')?.textContent.trim() === name,
  );

  const setStatus = (card, text) => {
    const status = card?.querySelector('.status');
    if (status) status.textContent = text;
  };

  document.addEventListener('DOMContentLoaded', async () => {
    const openmaic = cardByName('OpenMAIC');
    const deeptutor = cardByName('DeepTutor');
    try {
      const response = await fetch('/api/learning/status', {cache: 'no-store'});
      if (!response.ok) throw new Error('status unavailable');
      const status = await response.json();
      setStatus(
        openmaic,
        status.openmaic?.online && status.openmaic?.llm
          ? '互动课堂可用'
          : status.openmaic?.online
            ? '服务运行中，模型待确认'
            : '互动课堂未启动',
      );
      setStatus(
        deeptutor,
        status.deeptutor?.online && status.deeptutor?.llm ? '学习导师可用' : '学习导师需配置',
      );
    } catch {
      setStatus(openmaic, '状态未知');
      setStatus(deeptutor, '状态未知');
    }
  });
})();
