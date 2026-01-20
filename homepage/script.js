document.addEventListener('DOMContentLoaded', function () {

    /* Before/After Slider */
    // Select all sliders on the page
    const sliders = document.querySelectorAll('.comparison-slider');

    sliders.forEach(slider => {
        const overlay = slider.querySelector('.overlay');
        const overlayImg = overlay ? overlay.querySelector('img') : null;
        const handle = slider.querySelector('.handle');

        if (overlay && handle) {
            let isDragging = false;

            // Fix image width to match container width to prevent zooming effect
            // Use ResizeObserver for more robust handling of layout changes
            const updateImageWidth = () => {
                if (overlayImg) {
                    overlayImg.style.width = `${slider.offsetWidth}px`;
                }
            };

            // Initial call
            updateImageWidth();

            const resizeObserver = new ResizeObserver(entries => {
                for (let entry of entries) {
                    updateImageWidth();
                }
            });

            resizeObserver.observe(slider);

            const moveSlider = (e) => {
                if (!isDragging) return;
                e.preventDefault();

                const rect = slider.getBoundingClientRect();
                let x = (e.type === 'touchmove') ? e.touches[0].clientX : e.clientX;
                let position = ((x - rect.left) / rect.width) * 100;

                if (position < 0) position = 0;
                if (position > 100) position = 100;

                overlay.style.width = `${position}%`;
                handle.style.left = `${position}%`;
            };

            // Start dragging ONLY on handle
            const startDrag = (e) => {
                isDragging = true;
                e.stopPropagation(); // Prevent other events
                e.preventDefault();  // Prevent selection
            };

            handle.addEventListener('mousedown', startDrag);
            handle.addEventListener('touchstart', startDrag);

            // Global move/up events to handle dragging outside the element
            window.addEventListener('mouseup', () => isDragging = false);
            window.addEventListener('touchend', () => isDragging = false);

            window.addEventListener('mousemove', moveSlider);
            window.addEventListener('touchmove', moveSlider);
        }
    });

    // Optional: Log for debugging
    console.log('Homepage script loaded. Found ' + sliders.length + ' sliders.');
});
