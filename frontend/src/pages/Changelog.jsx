import React, { useState, useEffect } from 'react';
import axios from 'axios';

const Changelog = () => {
  const [changelog, setChangelog] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchChangelog();
  }, []);

  const fetchChangelog = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/changelog');
      setChangelog(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching changelog:', error);
      setLoading(false);
    }
  };

  const getCategoryColor = (category) => {
    const colors = {
      feature: '#10b981',
      bugfix: '#ef4444',
      improvement: '#3b82f6',
      breaking: '#f59e0b'
    };
    return colors[category] || '#6b7280';
  };

  const getImpactBadge = (impact) => {
    const styles = {
      critical: { bg: '#dc2626', text: 'white' },
      major: { bg: '#f59e0b', text: 'white' },
      minor: { bg: '#3b82f6', text: 'white' }
    };
    return styles[impact] || styles.minor;
  };

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Loading changelog...</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: '900px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '10px' }}>
        System Changelog
      </h1>
      <p style={{ color: '#6b7280', marginBottom: '30px' }}>
        Track all system improvements, new features, and bugfixes
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {changelog.map((entry) => {
          const impactStyle = getImpactBadge(entry.impact);
          return (
            <div
              key={entry.id}
              style={{
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '20px',
                backgroundColor: 'white'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between', marginBottom: '10px' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                    <span
                      style={{
                        backgroundColor: getCategoryColor(entry.category),
                        color: 'white',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: '600',
                        textTransform: 'uppercase'
                      }}
                    >
                      {entry.category}
                    </span>
                    <span
                      style={{
                        backgroundColor: impactStyle.bg,
                        color: impactStyle.text,
                        padding: '4px 8px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        fontWeight: '600'
                      }}
                    >
                      {entry.impact}
                    </span>
                    <span style={{ color: '#6b7280', fontSize: '12px' }}>
                      v{entry.version}
                    </span>
                  </div>
                  <h2 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px' }}>
                    {entry.title}
                  </h2>
                </div>
                <div style={{ textAlign: 'right', fontSize: '12px', color: '#6b7280' }}>
                  <div>{new Date(entry.created_at).toLocaleDateString()}</div>
                  <div>{new Date(entry.created_at).toLocaleTimeString()}</div>
                </div>
              </div>

              <div
                style={{
                  color: '#374151',
                  lineHeight: '1.6',
                  whiteSpace: 'pre-wrap'
                }}
              >
                {entry.description}
              </div>

              <div style={{ marginTop: '10px', fontSize: '12px', color: '#6b7280' }}>
                By {entry.author}
              </div>
            </div>
          );
        })}
      </div>

      {changelog.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>
          No changelog entries yet.
        </div>
      )}
    </div>
  );
};

export default Changelog;
