(function () {
  'use strict';

  var root = document.querySelector('.job-search');
  if (!root) return;

  var panel = document.getElementById('job-search-panel');
  var layout = document.getElementById('job-search-layout');
  var mapWrap = document.getElementById('job-map-wrap');
  var mapEl = document.getElementById('job-map');
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

  if (!panel || !layout || !mapWrap || !mapEl || !listCol || !countEl) return;

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

    var jobsById = {};
    jobs.forEach(function (j) {
      if (cardsById[j.id]) jobsById[j.id] = j;
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
        applyFilters();
      });
    }

    if (facilityFilterClear) {
      facilityFilterClear.addEventListener('click', function () {
        state.facility = null;
        setFacilityFilter(null);
        applyFilters();
      });
    }

    function restoreOriginalOrder() {
      originalOrder.forEach(function (li) {
        listCol.querySelector('.job-list__cards').appendChild(li);
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
        var sorted = jobs
          .filter(function (job) { return !cardsById[job.id].hidden; })
          .sort(function (a, b) {
            return (state.distances[a.facilityKey] || Infinity) - (state.distances[b.facilityKey] || Infinity);
          });
        var ul = listCol.querySelector('.job-list__cards');
        sorted.forEach(function (job) { ul.appendChild(cardsById[job.id]); });
      }

      countEl.textContent = visibleCount + ' 件を表示中';
      if (emptyMessage) emptyMessage.hidden = visibleCount !== 0;
      updateMarkers(visibleFacilityKeys);
    }

    // --- 地図(Leaflet) ---
    var markersByFacility = {};
    var mapInstance = null;

    function categoryClass(cats) {
      if (!cats || !cats.length) return 'job-map-marker--mixed';
      if (cats.length > 1) return 'job-map-marker--mixed';
      return 'job-map-marker--' + cats[0];
    }

    function updateMarkers(visibleFacilityKeys) {
      Object.keys(markersByFacility).forEach(function (key) {
        var marker = markersByFacility[key];
        var visible = !!visibleFacilityKeys[key];
        var el = marker.getElement && marker.getElement();
        if (el) el.style.opacity = visible ? '1' : '0.25';
      });
    }

    function initMap() {
      if (typeof window.L === 'undefined') {
        mapWrap.classList.add('job-map--fallback');
        mapWrap.hidden = false;
        return;
      }
      // Leaflet はコンテナの現在サイズを初期化時に測定するため、hidden 解除
      // (＝レイアウト確定) を map インスタンス生成より先に行う必要がある。
      // 順序を誤ると非表示(0サイズ)状態のまま初期化され、fitBounds が不正なズームで
      // 確定してしまう(実機検証で発覚)。
      mapWrap.hidden = false;
      layout.classList.add('job-search-layout--active');

      try {
        mapInstance = window.L.map(mapEl, {
          scrollWheelZoom: false,
        });
        window.L
          .tileLayer('https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png', {
            attribution:
              '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a>',
            maxZoom: 18,
          })
          .addTo(mapInstance);

        var bounds = [];
        Object.keys(facilities).forEach(function (key) {
          var f = facilities[key];
          var icon = window.L.divIcon({
            className: 'job-map-marker ' + categoryClass(f.categories),
            iconSize: [26, 26],
          });
          var marker = window.L.marker([f.lat, f.lng], { icon: icon }).addTo(mapInstance);
          marker.bindPopup(
            '<div class="job-map-popup">' +
              '<p class="job-map-popup__title">' + escapeHtml(f.name) + '</p>' +
              '<p class="job-map-popup__count">' + f.jobCount + ' 件の求人 ／ ' + escapeHtml(f.city) + '</p>' +
              '<button type="button" class="job-map-popup__link" data-facility-key="' + key + '">この拠点の求人だけ表示</button>' +
              '</div>'
          );
          marker.on('popupopen', function (e) {
            var btn = e.popup.getElement().querySelector('[data-facility-key]');
            if (btn) {
              btn.addEventListener('click', function () {
                state.facility = key;
                setFacilityFilter(key);
                applyFilters();
                highlightFacility(key);
              });
            }
          });
          marker.on('click', function () {
            highlightFacility(key);
          });
          markersByFacility[key] = marker;
          bounds.push([f.lat, f.lng]);
        });

        if (bounds.length) mapInstance.fitBounds(bounds, { padding: [24, 24] });
      } catch (e) {
        mapWrap.classList.add('job-map--fallback');
        mapWrap.hidden = false;
      }
    }

    function highlightFacility(key) {
      listCol.querySelectorAll('.job-list-card.is-highlighted').forEach(function (li) {
        li.classList.remove('is-highlighted');
      });
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

            if (mapInstance && window.L) {
              var nearestKey = Object.keys(distances).sort(function (a, b) {
                return distances[a] - distances[b];
              })[0];
              if (nearestKey) {
                var f = facilities[nearestKey];
                mapInstance.setView([f.lat, f.lng], 12, { animate: !reduceMotion });
              }
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

    initMap();
    applyFilters();
  }
})();
