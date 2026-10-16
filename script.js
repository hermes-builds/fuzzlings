/* Markerar aktiv sektion i navigeringen under scroll.
   Progressiv förbättring: utan JS fungerar sidan och länkarna precis
   lika bra, bara utan aktiv markering. */
(function () {
  'use strict';

  var links = Array.prototype.slice.call(
    document.querySelectorAll('.nav a[href^="#"]')
  );
  if (!links.length || typeof IntersectionObserver !== 'function') return;

  var byId = {};
  var targets = [];

  links.forEach(function (link) {
    var id = link.getAttribute('href').slice(1);
    var section = document.getElementById(id);
    if (!section) return;
    byId[id] = link;
    targets.push(section);
  });
  if (!targets.length) return;

  function setActive(id) {
    links.forEach(function (link) {
      if (link === byId[id]) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  }

  var observer = new IntersectionObserver(
    function (entries) {
      var best = null;
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        if (!best || entry.intersectionRatio > best.intersectionRatio) {
          best = entry;
        }
      });
      if (best && best.target.id) setActive(best.target.id);
    },
    { rootMargin: '-20% 0px -65% 0px', threshold: [0, 0.2, 0.6, 1] }
  );

  targets.forEach(function (section) {
    observer.observe(section);
  });
})();
