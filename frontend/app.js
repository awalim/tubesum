const API_URL = process.env.NODE_ENV === 'production' 
    ? 'https://your-backend-url.com' 
    : 'http://localhost:8000';

document.getElementById('summarizeBtn').addEventListener('click', async () => {
    const url = document.getElementById('videoUrl').value;
    const apiKey = document.getElementById('apiKey').value;
    const model = document.getElementById('model').value;
    
    if (!url) {
        alert('Please enter a YouTube URL');
        return;
    }
    
    // Show loading, hide results and error
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('results').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');
    
    try {
        const response = await fetch(`${API_URL}/transcript`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: url,
                api_key: apiKey || undefined,
                model: model
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch transcript');
        }
        
        const data = await response.json();
        
        // Display results
        document.getElementById('summary-text').innerHTML = data.summary || 'No API key provided for summary generation';
        document.getElementById('transcript-text').innerHTML = data.transcript || 'No transcript available';
        
        // Display steps (handle new idea/reality format or old string format)
        const stepsList = document.getElementById('steps-list');
        stepsList.innerHTML = '';
        if (data.steps && data.steps.length > 0) {
            data.steps.forEach(step => {
                const li = document.createElement('li');
                if (typeof step === 'object' && step.idea && step.reality) {
                    li.innerHTML = `<strong class="idea-label">The idea:</strong> ${step.idea}<br><strong class="reality-label">The reality:</strong> ${step.reality}`;
                } else {
                    li.textContent = step;
                }
                stepsList.appendChild(li);
            });
        } else {
            stepsList.innerHTML = '<li>No steps extracted (API key required)</li>';
        }
        
        // Display concepts (handle new name/description/url format)
        const conceptsList = document.getElementById('concepts-list');
        conceptsList.innerHTML = '';
        if (data.concepts && data.concepts.length > 0) {
            data.concepts.forEach(concept => {
                const li = document.createElement('li');
                if (typeof concept === 'object' && concept.name) {
                    let html = `<strong>${concept.name}</strong>`;
                    if (concept.description) html += `<p class="concept-desc">${concept.description}</p>`;
                    if (concept.url) html += `<a href="${concept.url}" target="_blank" class="concept-link">Link</a>`;
                    li.innerHTML = html;
                } else {
                    li.textContent = concept;
                }
                conceptsList.appendChild(li);
            });
        } else {
            conceptsList.innerHTML = '<li>No concepts extracted (API key required)</li>';
        }
        
        document.getElementById('results').classList.remove('hidden');
    } catch (error) {
        document.getElementById('error').textContent = error.message;
        document.getElementById('error').classList.remove('hidden');
    } finally {
        document.getElementById('loading').classList.add('hidden');
    }
});

// Tab switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        // Remove active class from all tabs and contents
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        // Add active class to clicked tab
        btn.classList.add('active');
        
        // Show corresponding content
        const tabId = btn.dataset.tab;
        document.getElementById(tabId).classList.add('active');
    });
});
