// Main JavaScript for TTSFree

// Global variables
let currentAudioPlayer = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initFileUpload();
    initRangeSliders();
    initVoiceSelectors();
    initAudioPlayers();
});

// File upload functionality
function initFileUpload() {
    const fileUploadAreas = document.querySelectorAll('.file-upload-area');
    
    fileUploadAreas.forEach(area => {
        const input = area.querySelector('input[type="file"]');
        
        area.addEventListener('click', () => input.click());
        
        area.addEventListener('dragover', (e) => {
            e.preventDefault();
            area.classList.add('dragover');
        });
        
        area.addEventListener('dragleave', () => {
            area.classList.remove('dragover');
        });
        
        area.addEventListener('drop', (e) => {
            e.preventDefault();
            area.classList.remove('dragover');
            
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                updateFileList(input);
            }
        });
        
        input.addEventListener('change', () => updateFileList(input));
    });
}

function updateFileList(input) {
    const container = input.closest('.file-upload-area');
    const fileList = container.querySelector('.file-list');
    const placeholder = container.querySelector('.placeholder');
    
    if (!fileList) return;
    
    fileList.innerHTML = '';
    
    if (input.files.length > 0) {
        placeholder.style.display = 'none';
        
        for (let file of input.files) {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item d-flex align-items-center mb-2 p-2 bg-light rounded';
            fileItem.innerHTML = `
                <i class="fas fa-file-audio text-primary me-3"></i>
                <div class="flex-grow-1">
                    <div class="fw-bold">${file.name}</div>
                    <small class="text-muted">${formatFileSize(file.size)}</small>
                </div>
                <button type="button" class="btn btn-sm btn-danger remove-file">
                    <i class="fas fa-times"></i>
                </button>
            `;
            
            fileItem.querySelector('.remove-file').addEventListener('click', () => {
                // Create new FileList without this file
                const dt = new DataTransfer();
                for (let i = 0; i < input.files.length; i++) {
                    if (i !== Array.from(input.files).indexOf(file)) {
                        dt.items.add(input.files[i]);
                    }
                }
                input.files = dt.files;
                updateFileList(input);
            });
            
            fileList.appendChild(fileItem);
        }
    } else {
        placeholder.style.display = 'block';
    }
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Range sliders
function initRangeSliders() {
    document.querySelectorAll('input[type="range"]').forEach(slider => {
        const valueDisplay = slider.nextElementSibling?.querySelector('.range-value');
        if (valueDisplay) {
            updateRangeValue(slider, valueDisplay);
            slider.addEventListener('input', () => updateRangeValue(slider, valueDisplay));
        }
    });
}

function updateRangeValue(slider, display) {
    let value = slider.value;
    let suffix = '';
    
    switch(slider.name) {
        case 'rate':
            suffix = '%';
            break;
        case 'pitch':
            suffix = 'Hz';
            break;
        case 'volume':
            suffix = '%';
            break;
        case 'pause_duration':
            suffix = 'ms';
            break;
    }
    
    display.textContent = value + suffix;
}

// Voice selectors
function initVoiceSelectors() {
    document.querySelectorAll('.language-select').forEach(select => {
        select.addEventListener('change', async function() {
            const voiceSelect = document.getElementById(this.dataset.target);
            if (!voiceSelect) return;
            
            const language = this.value;
            
            try {
                const response = await fetch(`/api/voices?language=${language}`);
                const data = await response.json();
                
                if (data.success) {
                    voiceSelect.innerHTML = '<option value="">Select a voice...</option>';
                    data.voices.forEach(voice => {
                        const option = document.createElement('option');
                        option.value = voice.id;
                        option.textContent = `${voice.name} (${voice.gender}) - ${voice.style}`;
                        voiceSelect.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('Error loading voices:', error);
                showToast('Error loading voices', 'error');
            }
        });
    });
}

// Audio players
function initAudioPlayers() {
    document.querySelectorAll('audio').forEach(audio => {
        audio.addEventListener('play', function() {
            if (currentAudioPlayer && currentAudioPlayer !== this) {
                currentAudioPlayer.pause();
            }
            currentAudioPlayer = this;
        });
    });
}

// Show toast notification
function showToast(message, type = 'success') {
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'success'} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle'} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();
    
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}

// Show loading overlay
function showLoading(message = 'Processing...') {
    let overlay = document.getElementById('loadingOverlay');
    
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loadingOverlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `
            <div class="text-center">
                <div class="loading-spinner mb-3"></div>
                <div class="text-white">${message}</div>
            </div>
        `;
        document.body.appendChild(overlay);
    }
    
    overlay.style.display = 'flex';
}

// Hide loading overlay
function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

// TTS generation
async function generateTTS(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    const formData = new FormData(form);
    
    // Validate
    const text = formData.get('text');
    if (!text || text.trim().length === 0) {
        showToast('Please enter text', 'error');
        return;
    }
    
    showLoading('Generating audio...');
    
    try {
        const response = await fetch('/api/tts/generate', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(result.message);
            
            // Update credits display
            const creditsBadge = document.querySelector('.credits-badge');
            if (creditsBadge) {
                creditsBadge.textContent = `${result.credits_remaining} credits`;
            }
            
            // Show audio player
            const audioContainer = document.getElementById('audioPlayerContainer');
            if (audioContainer) {
                audioContainer.innerHTML = `
                    <div class="audio-player mt-4">
                        <h5>Generated Audio</h5>
                        <audio controls class="w-100 mt-3">
                            <source src="${result.audio_url}" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                        <div class="mt-3">
                            <a href="${result.audio_url}" class="btn btn-success" download="${result.filename}">
                                <i class="fas fa-download me-2"></i>Download Audio
                            </a>
                        </div>
                    </div>
                `;
                initAudioPlayers();
            }
        } else {
            showToast(result.message || 'Generation failed', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Generation failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// STT transcription
async function transcribeAudio(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    const formData = new FormData(form);
    
    // Validate file
    const fileInput = form.querySelector('input[type="file"]');
    if (!fileInput.files.length) {
        showToast('Please select an audio file', 'error');
        return;
    }
    
    showLoading('Transcribing audio...');
    
    try {
        const response = await fetch('/api/stt/transcribe', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(result.message);
            
            // Update credits display
            const creditsBadge = document.querySelector('.credits-badge');
            if (creditsBadge) {
                creditsBadge.textContent = `${result.credits_remaining} credits`;
            }
            
            // Show download link
            const resultContainer = document.getElementById('resultContainer');
            if (resultContainer) {
                resultContainer.innerHTML = `
                    <div class="alert alert-success">
                        <h5><i class="fas fa-check-circle me-2"></i>Transcription Complete!</h5>
                        <p class="mb-3">Your audio has been successfully transcribed.</p>
                        <a href="${result.download_url}" class="btn btn-success" download="${result.filename}">
                            <i class="fas fa-download me-2"></i>Download ${result.filename.split('.').pop().toUpperCase()}
                        </a>
                    </div>
                `;
            }
        } else {
            showToast(result.message || 'Transcription failed', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Transcription failed: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// Change language
async function changeLanguage(lang) {
    try {
        const formData = new FormData();
        formData.append('language', lang);
        
        await fetch('/api/user/update-profile', {
            method: 'POST',
            body: formData
        });
        
        window.location.reload();
    } catch (error) {
        console.error('Error changing language:', error);
    }
}

// Copy to clipboard
function copyToClipboard(text, element = null) {
    navigator.clipboard.writeText(text).then(() => {
        if (element) {
            const original = element.innerHTML;
            element.innerHTML = '<i class="fas fa-check me-2"></i>Copied!';
            setTimeout(() => element.innerHTML = original, 2000);
        }
        showToast('Copied to clipboard');
    }).catch(err => {
        console.error('Failed to copy: ', err);
        showToast('Failed to copy', 'error');
    });
}

// Preview voice
async function previewVoice(voiceId, text = "Hello, this is a preview of this voice.") {
    if (!text || text.trim().length === 0) {
        text = "Hello, this is a preview of this voice.";
    }
    
    showLoading('Generating preview...');
    
    try {
        const formData = new FormData();
        formData.append('text', text);
        formData.append('voice', voiceId);
        formData.append('output_format', 'mp3');
        formData.append('rate', 0);
        formData.append('pitch', 0);
        formData.append('volume', 100);
        formData.append('pause_duration', 300);
        
        const response = await fetch('/api/tts/generate', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Play preview
            const audio = new Audio(result.audio_url);
            audio.play();
            
            showToast('Playing preview...');
        } else {
            showToast('Preview generation failed', 'error');
        }
    } catch (error) {
        console.error('Error generating preview:', error);
        showToast('Preview failed', 'error');
    } finally {
        hideLoading();
    }
}

// Export functions to window
window.generateTTS = generateTTS;
window.transcribeAudio = transcribeAudio;
window.copyToClipboard = copyToClipboard;
window.previewVoice = previewVoice;
window.changeLanguage = changeLanguage;
window.showToast = showToast;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
