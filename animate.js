document.addEventListener('DOMContentLoaded', function () {
    function animateValue(el, start, end, duration, isFloat) {
        var range = end - start;
        var startTime = null;
        var decimalPlaces = isFloat ? 2 : 0;
        function step(timestamp) {
            if (!startTime) startTime = timestamp;
            var progress = Math.min((timestamp - startTime) / duration, 1);
            var value = start + (range * progress);
            el.textContent = isFloat ? value.toFixed(decimalPlaces) : Math.round(value);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                el.textContent = isFloat ? end.toFixed(decimalPlaces) : end;
            }
        }
        window.requestAnimationFrame(step);
    }

    function runCountups() {
        var els = document.querySelectorAll('.countup');
        els.forEach(function(el) {
            var targetAttr = el.getAttribute('data-target');
            if (!targetAttr) return;
            var isFloat = targetAttr.indexOf('.') >= 0;
            var target = isFloat ? parseFloat(targetAttr) : parseInt(targetAttr, 10);
            // prevent re-animating if already reached target
            var current = parseFloat(el.textContent.replace(',', '')) || 0;
            if (Math.abs(current - target) < 1e-6) return;
            animateValue(el, 0, target, 900, isFloat);
        });
    }

    // Observe DOM mutations to animate when elements are added
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(m) {
            runCountups();
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Also run once on load
    runCountups();
});
