document.addEventListener('DOMContentLoaded', function () {
    const voiceSearchBtn = document.getElementById('voice-search-btn');
    const searchInput = document.getElementById('search-input');
    const voiceAnimation = document.getElementById('voice-animation');
    const searchResults = document.getElementById('search-results');

    let recognition;

    if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = function () {
            voiceAnimation.style.display = 'flex';
            voiceSearchBtn.classList.add('btn-danger');
            voiceSearchBtn.innerHTML = '<i class="fas fa-stop"></i>';
        };

        recognition.onresult = function (event) {
            searchInput.value = event.results[0][0].transcript;
            voiceAnimation.style.display = 'none';
            voiceSearchBtn.classList.remove('btn-danger');
            voiceSearchBtn.innerHTML = '<i class="fas fa-microphone"></i>';

            // Trigger search
            searchInput.form.submit();
        };

        recognition.onerror = function (event) {
            console.error('Speech recognition error:', event.error);
            voiceAnimation.style.display = 'none';
            voiceSearchBtn.classList.remove('btn-danger');
            voiceSearchBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        };

        recognition.onend = function () {
            voiceAnimation.style.display = 'none';
            voiceSearchBtn.classList.remove('btn-danger');
            voiceSearchBtn.innerHTML = '<i class="fas fa-microphone"></i>';
        };

        voiceSearchBtn.addEventListener('click', function () {
            if (recognition.isStarted) {
                recognition.stop();
            } else {
                recognition.start();
            }
        });
    } else {
        voiceSearchBtn.style.display = 'none';
        console.log('Web Speech API is not supported in this browser.');
    }

    // Add animation to search results
    function animateSearchResults() {
        const results = searchResults.children;
        for (let i = 0; i < results.length; i++) {
            results[i].classList.add('search-result-appear');
            results[i].style.animationDelay = `${i * 0.1}s`;
        }
    }

    // Call the animation function when the page loads
    animateSearchResults();
});

