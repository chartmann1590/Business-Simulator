/**
 * Timezone utility functions for formatting timestamps in the configured timezone.
 * Defaults to America/New_York timezone.
 */

// Get the configured timezone (default: America/New_York)
// This can be made configurable via environment variable or API call
const CONFIGURED_TIMEZONE = 'America/New_York'

/**
 * Format a timestamp in the configured timezone
 * @param {string|Date} timestamp - ISO string or Date object
 * @param {object} options - Intl.DateTimeFormat options
 * @returns {string} Formatted date string
 */
export function formatTimestamp(timestamp, options = {}) {
  if (!timestamp) {
    return new Date().toLocaleString('en-US', {
      timeZone: CONFIGURED_TIMEZONE,
      ...options
    })
  }

  try {
    const date = new Date(timestamp)
    if (isNaN(date.getTime())) {
      return new Date().toLocaleString('en-US', {
        timeZone: CONFIGURED_TIMEZONE,
        ...options
      })
    }
    
    return date.toLocaleString('en-US', {
      timeZone: CONFIGURED_TIMEZONE,
      ...options
    })
  } catch {
    return new Date().toLocaleString('en-US', {
      timeZone: CONFIGURED_TIMEZONE,
      ...options
    })
  }
}

/**
 * Format a timestamp as a date string in the configured timezone
 * @param {string|Date} timestamp - ISO string or Date object
 * @returns {string} Formatted date string
 */
export function formatDate(timestamp) {
  return formatTimestamp(timestamp, {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric'
  })
}

/**
 * Format a timestamp as a time string in the configured timezone
 * @param {string|Date} timestamp - ISO string or Date object
 * @returns {string} Formatted time string
 */
export function formatTime(timestamp) {
  return formatTimestamp(timestamp, {
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
    hour12: true
  })
}

/**
 * Format a timestamp as a date and time string in the configured timezone
 * @param {string|Date} timestamp - ISO string or Date object
 * @returns {string} Formatted date and time string
 */
export function formatDateTime(timestamp) {
  return formatTimestamp(timestamp, {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
    hour12: true
  })
}




