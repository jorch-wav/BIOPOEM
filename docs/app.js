// BioPoem Gallery - Main App
class BioPoem {
    constructor() {
        this.poems = [];
        this.currentFilter = 'all';
        this.ratings = {};
        this.currentModalPoem = null;
        this.modalImages = [];
        this.currentImageIndex = 0;
        // Backend API configuration
        this.apiUrl = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
            ? 'http://localhost:5000/api'
            : 'http://192.168.0.242:5000/api';
        this.init();
    }

    async init() {
        await this.loadPoems();
        await this.loadAllRatings();
        this.setupEventListeners();
        this.renderPoems();
        this.updateStats();
    }

    async loadPoems() {
        try {
            const response = await fetch('poems.json');
            this.poems = await response.json();
            console.log(`Loaded ${this.poems.length} poems`);
        } catch (error) {
            console.error('Error loading poems:', error);
            document.getElementById('loading').textContent = 'Error loading poems. Please try again later.';
        }
    }

    setupEventListeners() {
        // Filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.currentFilter = e.target.dataset.filter;
                this.renderPoems();
            });
        });
    }

    renderPoems() {
        const gallery = document.getElementById('gallery');
        const loading = document.getElementById('loading');
        const noResults = document.getElementById('no-results');
        
        loading.style.display = 'none';
        
        let filteredPoems;
        if (this.currentFilter === 'all') {
            filteredPoems = this.poems;
        } else if (this.currentFilter === 'rated') {
            // Show only poems with ratings
            filteredPoems = this.poems.filter(p => {
                const rating = this.ratings[p.id];
                return rating && (rating.likes > 0 || rating.dislikes > 0);
            });
        } else {
            filteredPoems = this.poems.filter(p => p.theme === this.currentFilter);
        }
        
        if (filteredPoems.length === 0) {
            gallery.innerHTML = '';
            noResults.style.display = 'block';
            return;
        }
        
        noResults.style.display = 'none';
        
        gallery.innerHTML = filteredPoems.map(poem => this.createPoemCard(poem)).join('');
        
        // Attach rating event listeners
        this.attachRatingListeners();
    }

    createPoemCard(poem) {
        const ratings = this.ratings[poem.id] || { likes: 0, dislikes: 0, comments: [] };
        // Ensure comments array exists (backwards compatibility)
        if (!ratings.comments) {
            ratings.comments = [];
        }
        const userRating = this.getUserRating(poem.id);
        const themeDisplay = this.getThemeDisplayName(poem.theme);
        
        return `
            <div class="poem-card" data-id="${poem.id}">
                <img src="${poem.image}" alt="${poem.title}" class="poem-image" onclick="window.app.openPoemModal('${poem.id}')">
                <div class="poem-info">
                    <div class="poem-date">${this.formatDate(poem.date)}</div>
                    <span class="poem-theme ${poem.theme}">${themeDisplay}</span>
                    <div class="rating-system">
                        <button class="rating-btn like-btn ${userRating === 'like' ? 'active' : ''}" data-id="${poem.id}" data-type="like" title="Rate this poem" aria-label="Like poem">
                            <span>👍</span>
                            <span class="rating-count">${ratings.likes}</span>
                        </button>
                        <button class="rating-btn dislike-btn ${userRating === 'dislike' ? 'active' : ''}" data-id="${poem.id}" data-type="dislike" title="Rate this poem" aria-label="Dislike poem">
                            <span>👎</span>
                            <span class="rating-count">${ratings.dislikes}</span>
                        </button>
                    </div>
                    <div class="comment-form" id="comment-form-${poem.id}" data-rating-type="">
                        <div class="comment-prompt" id="comment-prompt-${poem.id}">Please tell us why:</div>
                        <textarea class="comment-input" id="comment-input-${poem.id}" maxlength="280" placeholder="Explain your rating..." aria-label="Comment text"></textarea>
                        <div class="char-count"><span id="char-count-${poem.id}">0</span>/280</div>
                        <div class="comment-actions">
                            <button class="comment-submit" data-id="${poem.id}">Submit Rating</button>
                            <button class="comment-cancel" data-id="${poem.id}">Cancel</button>
                        </div>
                    </div>
                </div>
                ${this.createCommentsPreview(poem.id, ratings)}
            </div>
        `;
    }
    
    async openPoemModal(poemId) {
        const poem = this.poems.find(p => p.id === poemId);
        if (!poem) return;
        
        this.currentModalPoem = poem;
        this.currentImageIndex = 0;
        
        // Build images array: primary + additional renders
        this.modalImages = [
            { src: poem.image, label: 'Poem' }
        ];
        
        if (poem.additional_renders && poem.additional_renders.length > 0) {
            poem.additional_renders.forEach(render => {
                this.modalImages.push({ src: render.src, label: render.label });
            });
        }
        
        // Update modal content
        document.getElementById('modal-title').textContent = poem.title;
        document.getElementById('modal-date').textContent = this.formatDate(poem.date);
        document.getElementById('modal-theme').innerHTML = `<span class="poem-theme ${poem.theme}">${this.getThemeDisplayName(poem.theme)}</span>`;
        
        this.updateModalImage();
        
        // Load and display comments
        await this.loadModalComments(poemId);
        
        // Show modal
        document.getElementById('poemModal').classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    updateModalImage() {
        const currentImage = this.modalImages[this.currentImageIndex];
        document.getElementById('modal-image').src = currentImage.src;
        document.getElementById('modal-image-label').textContent = currentImage.label;
        document.getElementById('modal-counter').textContent = 
            `${this.currentImageIndex + 1} / ${this.modalImages.length}`;
    }

    attachRatingListeners() {
        document.querySelectorAll('.rating-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const button = e.currentTarget;
                const poemId = button.dataset.id;
                const type = button.dataset.type;
                this.showCommentFormForRating(poemId, type);
            });
        });
        
        // Comment input character counter
        document.querySelectorAll('.comment-input').forEach(input => {
            input.addEventListener('input', (e) => {
                const poemId = e.target.id.replace('comment-input-', '');
                const charCount = document.getElementById(`char-count-${poemId}`);
                charCount.textContent = e.target.value.length;
            });
        });
        
        // Comment submit buttons
        document.querySelectorAll('.comment-submit').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const poemId = e.currentTarget.dataset.id;
                this.submitComment(poemId);
            });
        });
        
        // Comment cancel buttons
        document.querySelectorAll('.comment-cancel').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const poemId = e.currentTarget.dataset.id;
                this.closeCommentForm(poemId);
            });
        });
    }


    
    showCommentFormForRating(poemId, ratingType) {
        // Check if user already rated this poem
        const currentRating = this.getUserRating(poemId);
        if (currentRating === ratingType) {
            // User is trying to un-rate - just remove the rating without comment
            this.handleUnrating(poemId);
            return;
        }
        
        if (currentRating && currentRating !== ratingType) {
            // User is changing their rating - require new comment
            if (!confirm('You already rated this poem. Change your rating and add a new comment?')) {
                return;
            }
        }
        
        // Show comment form with context
        const form = document.getElementById(`comment-form-${poemId}`);
        const prompt = document.getElementById(`comment-prompt-${poemId}`);
        const input = document.getElementById(`comment-input-${poemId}`);
        
        // Store the pending rating type
        form.dataset.ratingType = ratingType;
        
        // Update prompt based on rating type
        if (ratingType === 'like') {
            prompt.textContent = '👍 What did you like about this poem?';
            input.placeholder = 'e.g., "Direct language, felt genuine" or "Loved the imagery"';
        } else {
            prompt.textContent = '👎 What felt off about this poem?';
            input.placeholder = 'e.g., "Felt repetitive" or "Too abstract, unclear meaning"';
        }
        
        form.classList.add('active');
        input.value = '';
        input.focus();
        document.getElementById(`char-count-${poemId}`).textContent = '0';
    }
    
    closeCommentForm(poemId) {
        const form = document.getElementById(`comment-form-${poemId}`);
        const input = document.getElementById(`comment-input-${poemId}`);
        if (form) {
            form.classList.remove('active');
            form.dataset.ratingType = '';
            input.value = '';
        }
    }
    
    async handleUnrating(poemId) {
        const userId = this.getUserId();
        const currentRating = this.getUserRating(poemId);
        
        try {
            // Send un-rating (same type as current = toggle off)
            const response = await fetch(`${this.apiUrl}/rate/${poemId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: currentRating,
                    userId: userId
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to remove rating');
            }
            
            const result = await response.json();
            
            // Update local cache
            this.ratings[poemId] = {
                likes: result.likes,
                dislikes: result.dislikes,
                comments: this.ratings[poemId]?.comments || []
            };
            
            // Remove user rating tracking
            this.removeUserRating(poemId);
            
            this.renderPoems();
            this.updateStats();
        } catch (error) {
            console.error('Error removing rating:', error);
            alert('Failed to remove rating. Please try again.');
        }
    }
    
    async submitComment(poemId) {
        const input = document.getElementById(`comment-input-${poemId}`);
        const comment = input.value.trim();
        const form = document.getElementById(`comment-form-${poemId}`);
        const ratingType = form.dataset.ratingType;
        
        // Validate comment
        if (comment.length === 0) {
            alert('Please explain your rating before submitting.');
            input.focus();
            return;
        }
        
        if (comment.length < 10) {
            alert('Please provide more detail (at least 10 characters).');
            input.focus();
            return;
        }
        
        if (!ratingType) {
            alert('Error: No rating type selected. Please try again.');
            this.closeCommentForm(poemId);
            return;
        }
        
        const userId = this.getUserId();
        
        try {
            // Submit rating and comment together
            const ratingResponse = await fetch(`${this.apiUrl}/rate/${poemId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    type: ratingType,
                    userId: userId
                })
            });
            
            if (!ratingResponse.ok) {
                throw new Error('Failed to save rating');
            }
            
            const ratingResult = await ratingResponse.json();
            
            // Now submit the comment
            const commentResponse = await fetch(`${this.apiUrl}/comment/${poemId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: comment,
                    userId: userId
                })
            });
            
            if (!commentResponse.ok) {
                throw new Error('Failed to save comment');
            }
            
            const commentResult = await commentResponse.json();
            
            // Update local cache
            this.ratings[poemId] = {
                likes: ratingResult.likes,
                dislikes: ratingResult.dislikes,
                comments: this.ratings[poemId]?.comments || []
            };
            this.ratings[poemId].comments.push(commentResult.comment);
            
            // Update user rating tracking
            this.setUserRating(poemId, ratingType);
            
            // Close form and refresh
            this.closeCommentForm(poemId);
            this.renderPoems();
            this.updateStats();
            
            // Show success feedback
            const btn = document.querySelector(`.rating-btn[data-id="${poemId}"][data-type="${ratingType}"]`);
            if (btn) {
                btn.style.transform = 'scale(1.2)';
                setTimeout(() => {
                    btn.style.transform = '';
                }, 300);
            }
            
        } catch (error) {
            console.error('Error saving rating/comment:', error);
            alert('Failed to save your feedback. Please try again.');
        }
    }
    
    hasUserComment(poemId) {
        const userId = this.getUserId();
        const ratings = this.ratings[poemId];
        if (!ratings || !ratings.comments || !Array.isArray(ratings.comments)) return false;
        return ratings.comments.some(c => c.userId === userId);
    }
    
    getUserId() {
        let userId = localStorage.getItem('biopoem_user_id');
        if (!userId) {
            userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('biopoem_user_id', userId);
        }
        return userId;
    }

    async loadAllRatings() {
        // Load ratings for all poems from backend
        const loadPromises = this.poems.map(poem => this.loadRating(poem.id));
        await Promise.all(loadPromises);
    }

    async loadRating(poemId) {
        try {
            const response = await fetch(`${this.apiUrl}/feedback/${poemId}`);
            if (response.ok) {
                const data = await response.json();
                this.ratings[poemId] = data;
            }
        } catch (error) {
            console.error(`Error loading rating for ${poemId}:`, error);
            // Fallback to empty rating
            this.ratings[poemId] = { likes: 0, dislikes: 0, comments: [] };
        }
    }

    getUserRating(poemId) {
        const userRatings = JSON.parse(localStorage.getItem('biopoem_user_ratings') || '{}');
        return userRatings[poemId];
    }

    setUserRating(poemId, type) {
        const userRatings = JSON.parse(localStorage.getItem('biopoem_user_ratings') || '{}');
        userRatings[poemId] = type;
        localStorage.setItem('biopoem_user_ratings', JSON.stringify(userRatings));
    }

    removeUserRating(poemId) {
        const userRatings = JSON.parse(localStorage.getItem('biopoem_user_ratings') || '{}');
        delete userRatings[poemId];
        localStorage.setItem('biopoem_user_ratings', JSON.stringify(userRatings));
    }

    async updateStats() {
        document.getElementById('total-poems').textContent = this.poems.length;
        
        // Calculate days running from project start (November 2024)
        const startDate = new Date('2024-11-01');
        const today = new Date();
        const days = Math.floor((today - startDate) / (1000 * 60 * 60 * 24));
        document.getElementById('days-running').textContent = days;
        
        // Get total interactions from backend
        try {
            const response = await fetch(`${this.apiUrl}/stats`);
            if (response.ok) {
                const stats = await response.json();
                document.getElementById('total-interactions').textContent = stats.total_ratings;
            } else {
                // Fallback to local calculation
                const totalInteractions = Object.values(this.ratings).reduce((sum, r) => sum + r.likes + r.dislikes, 0);
                document.getElementById('total-interactions').textContent = totalInteractions;
            }
        } catch (error) {
            console.error('Error loading stats:', error);
            // Fallback to local calculation
            const totalInteractions = Object.values(this.ratings).reduce((sum, r) => sum + r.likes + r.dislikes, 0);
            document.getElementById('total-interactions').textContent = totalInteractions;
        }
    }

    getThemeDisplayName(themeKey) {
        const themeNames = {
            'thirsting': 'Dry',
            'enduring': 'Low',
            'sustained': 'Comfortable',
            'sated': 'Wet',
            'recovering': 'Bouncing Back'
        };
        return themeNames[themeKey] || themeKey;
    }

    createCommentsPreview(poemId, ratings) {
        if (!ratings || !ratings.comments || ratings.comments.length === 0) {
            return '';
        }
        
        const count = ratings.comments.length;
        return `
            <div class="comments-preview">
                <button class="view-comments-btn" onclick="app.openPoemModal('${poemId}')">
                    💬 View ${count} comment${count !== 1 ? 's' : ''}
                </button>
            </div>
        `;
    }
    
    async loadModalComments(poemId) {
        const commentsSection = document.getElementById('modal-comments');
        const commentsList = document.getElementById('modal-comments-list');
        
        try {
            const response = await fetch(`${this.apiUrl}/feedback/${poemId}`);
            if (!response.ok) throw new Error('Failed to load comments');
            
            const data = await response.json();
            
            if (!data.comments || data.comments.length === 0) {
                commentsSection.style.display = 'none';
                return;
            }
            
            // Display comments
            commentsList.innerHTML = data.comments.map(comment => {
                const date = new Date(comment.timestamp);
                const timeAgo = this.getTimeAgo(date);
                
                // Get rating type from user_ratings if available
                const icon = '💭'; // Default
                
                return `
                    <div class="comment-item">
                        <div class="comment-header">
                            <span class="comment-icon">${icon}</span>
                            <span class="comment-time">${timeAgo}</span>
                        </div>
                        <div class="comment-text">${this.escapeHtml(comment.text)}</div>
                    </div>
                `;
            }).join('');
            
            commentsSection.style.display = 'block';
        } catch (error) {
            console.error('Error loading comments:', error);
            commentsSection.style.display = 'none';
        }
    }
    
    getTimeAgo(date) {
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        
        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        if (seconds < 2592000) return `${Math.floor(seconds / 86400)}d ago`;
        return date.toLocaleDateString();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric' 
        });
    }
}

// Initialize app when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new BioPoem();
    window.app = app; // Make it globally accessible for onclick handlers
});

// Modal functions
function closeModal() {
    document.getElementById('poemModal').classList.remove('active');
    document.body.style.overflow = '';
}

function previousImage() {
    if (app && app.currentImageIndex > 0) {
        app.currentImageIndex--;
        app.updateModalImage();
    }
}

function nextImage() {
    if (app && app.currentImageIndex < app.modalImages.length - 1) {
        app.currentImageIndex++;
        app.updateModalImage();
    }
}

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
    }
    if (document.getElementById('poemModal').classList.contains('active')) {
        if (e.key === 'ArrowLeft') {
            previousImage();
        } else if (e.key === 'ArrowRight') {
            nextImage();
        }
    }
});
