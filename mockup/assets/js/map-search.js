(function () {
  'use strict';

  var root = document.querySelector('.job-search');
  if (!root) return;

  var panel = document.getElementById('job-search-panel');
  var mapWrap = document.getElementById('job-map-wrap');
  var diagramEl = document.getElementById('job-map-diagram');
  var listCol = document.getElementById('job-search-list-col');
  var countEl = document.getElementById('job-search-count');
  var freewordEl = document.getElementById('job-search-freeword');
  var gpsBtn = document.getElementById('job-search-gps');
  var clearBtn = document.getElementById('job-search-clear');
  var gpsStatus = document.getElementById('job-search-gps-status');
  var facilityFilterBar = document.getElementById('job-search-facility-filter');
  var facilityFilterLabel = document.getElementById('job-search-facility-filter-label');
  var facilityFilterClear = document.getElementById('job-search-facility-filter-clear');
  var emptyMessage = document.getElementById('job-search-empty');

  if (!panel || !mapWrap || !diagramEl || !listCol || !countEl) return;

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var EARTH_RADIUS_KM = 6371;
  function haversineKm(lat1, lng1, lat2, lng2) {
    var toRad = function (d) { return (d * Math.PI) / 180; };
    var dLat = toRad(lat2 - lat1);
    var dLng = toRad(lng2 - lng1);
    var a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return EARTH_RADIUS_KM * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  fetch('assets/data/jobs.json')
    .then(function (res) {
      if (!res.ok) throw new Error('jobs.json fetch failed: ' + res.status);
      return res.json();
    })
    .then(function (data) {
      init(data);
    })
    .catch(function () {
      // データ取得失敗時は検索UI一式を出さず、既存の34カード全表示のままにする。
    });

  function init(data) {
    var facilities = data.facilities || {};
    var jobs = data.jobs || [];

    var cardsById = {};
    var originalOrder = [];
    listCol.querySelectorAll('.job-list-card').forEach(function (li) {
      var link = li.querySelector('.job-list-card__link');
      var href = link ? link.getAttribute('href') : '';
      var id = href ? href.split('/').pop().replace('.html', '') : null;
      if (!id) return;
      cardsById[id] = li;
      originalOrder.push(li);

      if (!li.querySelector('.job-list-card__distance')) {
        var badge = document.createElement('span');
        badge.className = 'job-list-card__distance';
        var body = li.querySelector('.job-list-card__body');
        if (body) body.insertBefore(badge, body.firstChild);
      }
    });

    var state = {
      category: new Set(),
      employment: new Set(),
      area: new Set(),
      facility: null,
      freeword: '',
      distances: null, // { [jobId]: km } while GPS active
    };

    panel.hidden = false;

    panel.querySelectorAll('.job-search-panel__chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        var group = chip.parentElement.getAttribute('data-filter-group');
        var value = chip.getAttribute('data-value');
        var set = state[group];
        var pressed = chip.getAttribute('aria-pressed') === 'true';
        chip.setAttribute('aria-pressed', String(!pressed));
        if (pressed) set.delete(value);
        else set.add(value);
        applyFilters();
      });
    });

    if (freewordEl) {
      freewordEl.addEventListener('input', function () {
        state.freeword = freewordEl.value.trim();
        applyFilters();
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        state.category.clear();
        state.employment.clear();
        state.area.clear();
        state.facility = null;
        state.freeword = '';
        state.distances = null;
        if (freewordEl) freewordEl.value = '';
        panel.querySelectorAll('.job-search-panel__chip').forEach(function (chip) {
          chip.setAttribute('aria-pressed', 'false');
        });
        root.setAttribute('data-gps-active', 'false');
        setGpsStatus('');
        restoreOriginalOrder();
        setFacilityFilter(null);
        clearHighlight();
        diagramEl.querySelectorAll('.job-map-pin.is-nearest').forEach(function (p) {
          p.classList.remove('is-nearest');
        });
        applyFilters();
      });
    }

    if (facilityFilterClear) {
      facilityFilterClear.addEventListener('click', function () {
        state.facility = null;
        setFacilityFilter(null);
        clearHighlight();
        applyFilters();
      });
    }

    function restoreOriginalOrder() {
      originalOrder.forEach(function (li) {
        listCol.querySelector('.job-list__cards').appendChild(li);
      });
    }

    function clearHighlight() {
      listCol.querySelectorAll('.job-list-card.is-highlighted').forEach(function (li) {
        li.classList.remove('is-highlighted');
      });
    }

    function setFacilityFilter(key) {
      if (!facilityFilterBar) return;
      if (!key) {
        facilityFilterBar.hidden = true;
        return;
      }
      var f = facilities[key];
      if (!f) return;
      facilityFilterBar.hidden = false;
      if (facilityFilterLabel) facilityFilterLabel.textContent = f.name + ' の求人のみ表示中';
    }

    function setGpsStatus(text, isError) {
      if (!gpsStatus) return;
      if (!text) {
        gpsStatus.hidden = true;
        gpsStatus.textContent = '';
        gpsStatus.removeAttribute('data-state');
        return;
      }
      gpsStatus.hidden = false;
      gpsStatus.textContent = text;
      if (isError) gpsStatus.setAttribute('data-state', 'error');
      else gpsStatus.removeAttribute('data-state');
    }

    function matchesFilters(job) {
      if (state.category.size && !state.category.has(job.category)) return false;
      if (state.area.size && !state.area.has(job.area)) return false;
      if (state.facility && job.facilityKey !== state.facility) return false;
      if (state.employment.size) {
        var hit = job.employment.some(function (e) { return state.employment.has(e); });
        if (!hit) return false;
      }
      if (state.freeword) {
        var li = cardsById[job.id];
        var text = li ? li.textContent.toLowerCase() : '';
        if (text.indexOf(state.freeword.toLowerCase()) === -1) return false;
      }
      return true;
    }

    function applyFilters() {
      var visibleCount = 0;
      var visibleFacilityKeys = {};

      jobs.forEach(function (job) {
        var li = cardsById[job.id];
        if (!li) return;
        var visible = matchesFilters(job);
        li.hidden = !visible;
        if (visible) {
          visibleCount += 1;
          visibleFacilityKeys[job.facilityKey] = true;

          if (state.distances) {
            var badge = li.querySelector('.job-list-card__distance');
            var km = state.distances[job.facilityKey];
            if (badge && typeof km === 'number') {
              badge.textContent = '現在地から約 ' + km.toFixed(1) + ' km';
            }
          }
        }
      });

      if (state.distances) {
        var distanceOf = function (job) {
          var km = state.distances[job.facilityKey];
          return typeof km === 'number' ? km : Infinity;
        };
        var sorted = jobs
          .filter(function (job) { return cardsById[job.id] && !cardsById[job.id].hidden; })
          .sort(function (a, b) { return distanceOf(a) - distanceOf(b); });
        var ul = listCol.querySelector('.job-list__cards');
        sorted.forEach(function (job) { ul.appendChild(cardsById[job.id]); });
      }

      countEl.textContent = visibleCount + ' 件を表示中';
      if (emptyMessage) emptyMessage.hidden = visibleCount !== 0;
      updatePins(visibleFacilityKeys);
    }

    // --- 九州シルエット地図(2026-07-23決裁者フィードバック対応) ---
    // 第1弾(Leaflet+地理院タイル→白地図)でも「実地図画像である限りスタイリッシュな
    // トンマナと合わない」との指摘を受け、実地図を完全に廃止。assets/img/kyushu-map.svg
    // (geolonia/japanese-prefectures 由来、九州7県のみ抽出した簡略化シルエット)を
    // フラット単色の背景として使い、ピンは該当県(福岡=40/鹿児島=46)の重心座標
    // (SVG の viewBox に対するパーセント位置、ビルド時に一度だけ算出)にクラスタ表示する。
    // GPS距離計算自体は実緯度経度のHaversine計算のままで、可視化だけを分離している。
    var AREA_ORDER = ['fukuoka', 'kagoshima'];
    // 各エリアの代表県重心 (kyushu-map.svg の viewBox 内でのパーセント位置)
    var AREA_ANCHOR = {
      fukuoka: { left: 58.5, top: 29.9 },
      kagoshima: { left: 50.0, top: 75.7 },
    };
    var popupEl = null;

    function categoryClass(cats) {
      if (!cats || cats.length !== 1) return 'job-map-pin--mixed';
      return 'job-map-pin--' + cats[0];
    }

    function updatePins(visibleFacilityKeys) {
      diagramEl.querySelectorAll('.job-map-pin').forEach(function (pin) {
        var key = pin.getAttribute('data-facility-key');
        pin.classList.toggle('is-dimmed', !visibleFacilityKeys[key]);
      });
    }

    function closePopup() {
      if (popupEl) {
        popupEl.remove();
        popupEl = null;
      }
    }

    function showPopup(key, pinEl) {
      closePopup();
      var f = facilities[key];
      if (!f) return;
      var diagramRect = diagramEl.getBoundingClientRect();
      var pinRect = pinEl.getBoundingClientRect();

      popupEl = document.createElement('div');
      popupEl.className = 'job-map-popup';
      popupEl.innerHTML =
        '<button type="button" class="job-map-popup__close" aria-label="閉じる">×</button>' +
        '<p class="job-map-popup__title">' + escapeHtml(f.name) + '</p>' +
        '<p class="job-map-popup__count">' + f.jobCount + ' 件の求人 ／ ' + escapeHtml(f.city) + '</p>' +
        '<button type="button" class="job-map-popup__link" data-facility-key="' + key + '">この拠点の求人だけ表示</button>';
      diagramEl.appendChild(popupEl);

      var left = pinRect.left - diagramRect.left + pinRect.width / 2 - popupEl.offsetWidth / 2;
      var maxLeft = diagramRect.width - popupEl.offsetWidth - 8;
      popupEl.style.left = Math.max(8, Math.min(left, maxLeft)) + 'px';

      // 下段(鹿児島エリア等)のピンでは pin の下に表示すると .job-map-wrap の
      // overflow:hidden で吹き出しが切れて見えなくなるため、下に十分な余白が
      // ない場合は pin の上側に表示する(実機検証で発覚)。
      var top = pinRect.top - diagramRect.top + pinRect.height + 8;
      var popupHeight = popupEl.offsetHeight;
      if (top + popupHeight > diagramRect.height - 8) {
        top = Math.max(8, pinRect.top - diagramRect.top - popupHeight - 8);
      }
      popupEl.style.top = top + 'px';

      popupEl.querySelector('.job-map-popup__close').addEventListener('click', closePopup);
      popupEl.querySelector('.job-map-popup__link').addEventListener('click', function () {
        state.facility = key;
        setFacilityFilter(key);
        applyFilters();
        highlightFacility(key);
        closePopup();
      });
    }

    document.addEventListener('click', function (e) {
      if (!popupEl) return;
      if (popupEl.contains(e.target) || e.target.closest('.job-map-pin')) return;
      closePopup();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closePopup();
    });

    function buildPinClusters() {
      // 空エリア(拠点0件)はクラスタごと描画しない。
      var clustersHtml = AREA_ORDER.map(function (area) {
        var keys = Object.keys(facilities).filter(function (k) { return facilities[k].area === area; });
        if (!keys.length) return '';
        var anchor = AREA_ANCHOR[area];
        var html = '<div class="job-map-pin-cluster" data-area="' + area + '" style="left:' + anchor.left + '%;top:' + anchor.top + '%">';
        keys.forEach(function (key) {
          var f = facilities[key];
          html +=
            '<button type="button" class="job-map-pin ' + categoryClass(f.categories) + '" ' +
            'data-facility-key="' + key + '" aria-label="' + escapeHtml(f.name) + '"></button>';
        });
        html += '</div>';
        return html;
      }).join('');

      var wrap = document.createElement('div');
      wrap.innerHTML = clustersHtml;
      Array.prototype.slice.call(wrap.children).forEach(function (cluster) {
        diagramEl.appendChild(cluster);
      });

      diagramEl.querySelectorAll('.job-map-pin').forEach(function (pin) {
        pin.addEventListener('click', function (e) {
          e.stopPropagation();
          var key = pin.getAttribute('data-facility-key');
          showPopup(key, pin);
          highlightFacility(key);
        });
      });
    }

    function initDiagram() {
      fetch('assets/img/kyushu-map.svg')
        .then(function (res) {
          if (!res.ok) throw new Error('kyushu-map.svg fetch failed: ' + res.status);
          return res.text();
        })
        .then(function (svgText) {
          diagramEl.innerHTML = svgText;
          buildPinClusters();
          mapWrap.hidden = false;
        })
        .catch(function () {
          // 地図画像の取得・描画に失敗した場合は非表示のまま(フィルタ・求人一覧は影響を受けない)。
        });
    }

    function highlightFacility(key) {
      clearHighlight();
      var firstMatch = null;
      jobs.forEach(function (job) {
        if (job.facilityKey !== key) return;
        var li = cardsById[job.id];
        if (!li || li.hidden) return;
        li.classList.add('is-highlighted');
        if (!firstMatch) firstMatch = li;
      });
      if (firstMatch) {
        firstMatch.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
      }
    }

    function escapeHtml(str) {
      return String(str).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }

    // --- GPS ---
    if (gpsBtn) {
      gpsBtn.addEventListener('click', function () {
        if (!('geolocation' in navigator)) {
          setGpsStatus('この端末・ブラウザは現在地取得に対応していません。', true);
          return;
        }
        gpsBtn.disabled = true;
        setGpsStatus('現在地を取得しています…');

        navigator.geolocation.getCurrentPosition(
          function (pos) {
            var lat = pos.coords.latitude;
            var lng = pos.coords.longitude;
            var distances = {};
            Object.keys(facilities).forEach(function (key) {
              var f = facilities[key];
              distances[key] = haversineKm(lat, lng, f.lat, f.lng);
            });
            state.distances = distances;
            root.setAttribute('data-gps-active', 'true');
            setGpsStatus('現在地から近い順に並び替えました。');
            gpsBtn.disabled = false;

            diagramEl.querySelectorAll('.job-map-pin.is-nearest').forEach(function (p) {
              p.classList.remove('is-nearest');
            });
            var nearestKey = Object.keys(distances).sort(function (a, b) {
              return distances[a] - distances[b];
            })[0];
            if (nearestKey) {
              var nearestPin = diagramEl.querySelector('[data-facility-key="' + nearestKey + '"]');
              if (nearestPin) nearestPin.classList.add('is-nearest');
            }
            applyFilters();
          },
          function (err) {
            gpsBtn.disabled = false;
            if (err.code === err.PERMISSION_DENIED) {
              setGpsStatus('位置情報の利用が許可されませんでした。ブラウザの設定をご確認ください。', true);
            } else if (err.code === err.TIMEOUT) {
              setGpsStatus('現在地の取得がタイムアウトしました。もう一度お試しください。', true);
            } else {
              setGpsStatus('現在地を取得できませんでした。', true);
            }
          },
          { timeout: 8000 }
        );
      });
    }

    initDiagram();
    applyFilters();
  }
})();
