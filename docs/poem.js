// Poem Detail Page
class PoemDetail {
    constructor() {
        this.poemId = new URLSearchParams(window.location.search).get('id');
        this.poem = null;
        this.init();
    }

    async init() {
        await this.loadPoem();
        this.render();
    }

    async loadPoem() {
        try {
            const response = await fetch('poems.json');
            const poems = await response.json();
            this.poem = poems.find(p => p.id === this.poemId);
            
            if (!this.poem) {
                throw new Error('Poem not found');
            }
        } catch (error) {
            console.error('Error loading poem:', error);
            document.getElementById('poem-content').innerHTML = `
                <p>Poem not found. <a href="index.html">Return to gallery</a></p>
            `;
        }
    }

    render() {
        if (!this.poem) return;

        const content = document.getElementById('poem-content');
        content.innerHTML = `
            <div class="detail-hero">
                <h1>${this.poem.title || 'Untitled'}</h1>
                <div class="detail-meta">
                    <span>${this.formatDate(this.poem.date)}</span>
                    <span>•</span>
                    <span class="poem-theme ${this.poem.theme}">${this.poem.theme}</span>
                    <span>•</span>
                    <span>${this.poem.influence}</span>
                </div>
            </div>

            <section>
                <h2>Rendered Poems</h2>
                <div class="renders-grid">
                    ${this.renderImages()}
                </div>
            </section>

            ${this.poem.sensor_summary ? `
            <section class="sensor-summary">
                <h3>Sensor Summary</h3>
                <div class="sensor-grid">
                    ${this.renderSensorData()}
                </div>
            </section>
            ` : ''}

            ${this.poem.prompt ? `
            <section class="prompt-section">
                <h3>AI Prompt</h3>
                <div class="prompt-text">${this.escapeHtml(this.poem.prompt)}</div>
            </section>
            ` : ''}

            <section style="margin-top: 2rem;">
                <a href="index.html" class="back-link">← Back to Gallery</a>
            </section>
        `;
    }

    renderImages() {
        const images = [
            { src: this.poem.image, label: 'Main Render' },
            ...(this.poem.additional_renders || [])
        ];

        return images.map(img => `
            <div class="render-item">
                <img src="${img.src}" alt="${img.label}">
                <div class="render-label">${img.label}</div>
            </div>
        `).join('');
    }

    renderSensorData() {
        const data = this.poem.sensor_summary;
        return `
            <div class="sensor-item">
                <span class="sensor-label">Moisture</span>
                <span class="sensor-value">${data.moisture}</span>
            </div>
            <div class="sensor-item">
                <span class="sensor-label">Temperature</span>
                <span class="sensor-value">${data.temperature}</span>
            </div>
            <div class="sensor-item">
                <span class="sensor-label">Light</span>
                <span class="sensor-value">${data.light}</span>
            </div>
            <div class="sensor-item">
                <span class="sensor-label">Humidity</span>
                <span class="sensor-value">${data.humidity}</span>
            </div>
            <div class="sensor-item">
                <span class="sensor-label">Pressure</span>
                <span class="sensor-value">${data.pressure}</span>
            </div>
        `;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new PoemDetail();
});
