// ============================================================================
// INTEGRATION CODE FOR GOLD.KELASMASTER.ID
// Add this code to your React app to enable auto-posting queue
// ============================================================================

// 1. Add this API configuration
const API_CONFIG = {
  baseURL: 'http://YOUR_SERVER_IP:18794',  // Replace with actual server IP
  endpoints: {
    queuePost: '/api/queue-post',
    getQueue: '/api/queue',
    getFanspages: '/api/config'
  }
};

// 2. Add this function to queue posts for auto-posting
async function queueForAutoPost(caption, imageCanvas, selectedPageIds) {
  try {
    // Convert canvas to base64
    const imageDataURL = imageCanvas.toDataURL('image/png');
    
    // Send to API
    const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.queuePost}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        caption: caption,
        image_data: imageDataURL,
        page_ids: selectedPageIds
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      return {
        success: true,
        message: `✅ Queued for ${selectedPageIds.length} fanspage(s)!`,
        data: result
      };
    } else {
      return {
        success: false,
        message: `❌ Error: ${result.error}`,
        data: result
      };
    }
  } catch (error) {
    return {
      success: false,
      message: `❌ Network error: ${error.message}`,
      error: error
    };
  }
}

// 3. Add this function to get available fanspages
async function getFanspages() {
  try {
    const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.getFanspages}`);
    const result = await response.json();
    
    if (result.configured && result.fanspages) {
      return result.fanspages.filter(page => page.enabled);
    }
    return [];
  } catch (error) {
    console.error('Error fetching fanspages:', error);
    return [];
  }
}

// 4. Add this React component for the Queue Button
function QueueButton({ caption, imageCanvas, onSuccess, onError }) {
  const [loading, setLoading] = React.useState(false);
  const [fanspages, setFanspages] = React.useState([]);
  const [selectedPages, setSelectedPages] = React.useState([]);
  const [showModal, setShowModal] = React.useState(false);
  
  React.useEffect(() => {
    loadFanspages();
  }, []);
  
  async function loadFanspages() {
    const pages = await getFanspages();
    setFanspages(pages);
    // Select all by default
    setSelectedPages(pages.map(p => p.page_id));
  }
  
  async function handleQueue() {
    if (!caption || !imageCanvas) {
      alert('❌ Please generate caption and image first!');
      return;
    }
    
    if (selectedPages.length === 0) {
      alert('❌ Please select at least one fanspage!');
      return;
    }
    
    setLoading(true);
    
    const result = await queueForAutoPost(caption, imageCanvas, selectedPages);
    
    setLoading(false);
    
    if (result.success) {
      alert(result.message);
      setShowModal(false);
      if (onSuccess) onSuccess(result);
    } else {
      alert(result.message);
      if (onError) onError(result);
    }
  }
  
  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        disabled={loading || !caption || !imageCanvas}
        className="bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-6 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? '⏳ Queueing...' : '📤 Queue for Auto Post'}
      </button>
      
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full">
            <h3 className="text-xl font-bold text-yellow-500 mb-4">
              Select Fanspages
            </h3>
            
            <div className="space-y-2 mb-6">
              {fanspages.map(page => (
                <label key={page.page_id} className="flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedPages.includes(page.page_id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedPages([...selectedPages, page.page_id]);
                      } else {
                        setSelectedPages(selectedPages.filter(id => id !== page.page_id));
                      }
                    }}
                    className="mr-2"
                  />
                  <span className="text-white">{page.name}</span>
                </label>
              ))}
            </div>
            
            <div className="flex gap-3">
              <button
                onClick={handleQueue}
                disabled={loading || selectedPages.length === 0}
                className="flex-1 bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded transition disabled:opacity-50"
              >
                {loading ? 'Queueing...' : 'Queue'}
              </button>
              <button
                onClick={() => setShowModal(false)}
                disabled={loading}
                className="flex-1 bg-gray-600 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// 5. Export for use in your app
export { queueForAutoPost, getFanspages, QueueButton, API_CONFIG };

// ============================================================================
// USAGE EXAMPLE IN YOUR REACT APP:
// ============================================================================
/*

import { QueueButton } from './integration';

function YourComponent() {
  const [caption, setCaption] = useState('');
  const [imageCanvas, setImageCanvas] = useState(null);
  
  return (
    <div>
      // ... your existing code for generating caption and image ...
      
      <QueueButton 
        caption={caption}
        imageCanvas={imageCanvas}
        onSuccess={(result) => {
          console.log('Queued successfully:', result);
        }}
        onError={(error) => {
          console.error('Queue failed:', error);
        }}
      />
    </div>
  );
}

*/
