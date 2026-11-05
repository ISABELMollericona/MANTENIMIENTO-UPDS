(function () {
  const STATUS_ID = 'offline-status';
  const QUEUE_KEY = 'mant-queue';
  const KEEPALIVE_INTERVAL = 5 * 60 * 1000;

  function getQueue() {
    try {
      return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    } catch (error) {
      return [];
    }
  }

  function setQueue(items) {
    localStorage.setItem(QUEUE_KEY, JSON.stringify(items));
    updateStatus();
  }

  function updateStatus() {
    const status = document.getElementById(STATUS_ID);
    if (!status) {
      return;
    }
    const pending = getQueue().length;
    const online = navigator.onLine;
    status.classList.toggle('online', online);
    status.classList.toggle('offline', !online);
    status.textContent = online ? `En línea · ${pending} pendiente${pending === 1 ? '' : 's'}` : `Sin conexión · ${pending} pendiente${pending === 1 ? '' : 's'}`;
  }

  function queueOperation(operation) {
    const queue = getQueue();
    queue.push(operation);
    setQueue(queue);
  }

  function registerForms() {
    document.querySelectorAll('form[data-offline]').forEach(form => {
      form.addEventListener('submit', event => {
        const formData = new FormData(form);
        if (!navigator.onLine) {
          event.preventDefault();
          queueOperation({
            type: form.dataset.offline || 'solicitud',
            data: Object.fromEntries(formData.entries()),
            createdAt: new Date().toISOString(),
          });
          const alertBox = document.createElement('div');
          alertBox.className = 'alert alert-info mt-3';
          alertBox.textContent = 'Guardado en el dispositivo. Se enviará cuando haya conexión.';
          form.insertAdjacentElement('afterend', alertBox);
          form.reset();
          updateStatus();
        }
      });
    });
  }

  async function synchronize() {
    if (!navigator.onLine) {
      updateStatus();
      return;
    }
    const queue = getQueue();
    if (!queue.length) {
      updateStatus();
      return;
    }
    const current = queue[0];
    try {
      const response = await fetch('/api/offline/sincronizar/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.cookie.split('; ').find(part => part.startsWith('csrftoken='))?.split('=')[1] || '' },
        body: JSON.stringify({
          tipo: current.type,
          uuid_cliente: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`,
          fecha_cliente: current.createdAt,
          datos: current.data,
        }),
      });
      if (response.status === 401 || response.status === 403) {
        alert('Inicia sesión para terminar de enviar tus registros.');
        return;
      }
      if (response.ok) {
        const next = queue.slice(1);
        setQueue(next);
        await synchronize();
      }
    } catch (error) {
      updateStatus();
    }
  }

  function setupNetworkListeners() {
    window.addEventListener('online', () => {
      updateStatus();
      synchronize();
    });
    window.addEventListener('offline', updateStatus);
  }

  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) {
      return;
    }
    navigator.serviceWorker
      .register('/service-worker.js', { updateViaCache: 'none' })
      .then(registration => registration.update())
      .catch(() => undefined);
  }

  function startKeepAlive() {
    if (!document.getElementById(STATUS_ID)) {
      return;
    }

    window.setInterval(() => {
      if (!navigator.onLine) {
        return;
      }

      fetch('/api/keepalive/', { cache: 'no-store', credentials: 'same-origin' })
        .then(response => {
          if (!response.ok) {
            throw new Error(`Keep-alive request failed: ${response.status}`);
          }
        })
        .catch(() => updateStatus());
    }, KEEPALIVE_INTERVAL);
  }

  document.addEventListener('DOMContentLoaded', () => {
    updateStatus();
    registerForms();
    setupNetworkListeners();
    registerServiceWorker();
    startKeepAlive();
    const button = document.getElementById('sync-now-button');
    if (button) {
      button.addEventListener('click', synchronize);
    }
  });
})();
