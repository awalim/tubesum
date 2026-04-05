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
        
        // Display steps
        const stepsList = document.getElementById('steps-list');
        stepsList.innerHTML = '';
        if (data.steps && data.steps.length > 0) {
            data.steps.forEach(step => {
                const li = document.createElement('li');
                li.textContent = step;
                stepsList.appendChild(li);
            });
        } else {
            stepsList.innerHTML = '<li>No steps extracted (API key required)</li>';
        }
        
        // Display concepts
        const conceptsList = document.getElementById('concepts-list');
        conceptsList.innerHTML = '';
        if (data.concepts && data.concepts.length > 0) {
            data.concepts.forEach(concept => {
                const li = document.createElement('li');
                li.textContent = concept;
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
