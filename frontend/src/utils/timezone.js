/**
 * Timezone utility functions for formatting timestamps in the configured timezone.
 * Defaults to America/New_York timezone.
 */

// Get the configured timezone from environment variable or default
const DEFAULT_TIMEZONE = import.meta.env.VITE_TIMEZONE || 'America/New_York'

// Cache for timezone fetched from API
let CONFIGURED_TIMEZONE = DEFAULT_TIMEZONE
let timezoneFetchPromise = null

/**
 * Fetch timezone from API and cache it
 */
async function fetchTimezone() {
  if (timezoneFetchPromise) {
    return timezoneFetchPromise
  }
  
  timezoneFetchPromise = fetch('/api/config/timezone')
    .then(res => res.json())
    .then(data => {
      CONFIGURED_TIMEZONE = data.timezone || DEFAULT_TIMEZONE
      return CONFIGURED_TIMEZONE
    })
    .catch(() => {
      // Fallback to default if API fails
      CONFIGURED_TIMEZONE = DEFAULT_TIMEZONE
      return CONFIGURED_TIMEZONE
    })
    .finally(() => {
      timezoneFetchPromise = null
    })
  
  return timezoneFetchPromise
}

// Fetch timezone on module load
fetchTimezone()

/**
 * Get the configured timezone (async)
 * @returns {Promise<string>} The configured timezone
 */
export async function getTimezone() {
  await fetchTimezone()
  return CONFIGURED_TIMEZONE
}

/**
 * Format a timestamp in the configured timezone
 * @param {string|Date} timestamp - ISO string or Date object
 * @param {object} options - Intl.DateTimeFormat options
 * @returns {string} Formatted date string
 */
export function formatTimestamp(timestamp, options = {}) {
  // Ensure hour12 is always true unless explicitly set to false
  const formatOptions = {
    hour12: true,
    timeZone: CONFIGURED_TIMEZONE,
    ...options
  }
  
  if (!timestamp) {
    return new Date().toLocaleString('en-US', formatOptions)
  }

  try {
    const date = new Date(timestamp)
    if (isNaN(date.getTime())) {
      return new Date().toLocaleString('en-US', formatOptions)
    }
    
    return date.toLocaleString('en-US', formatOptions)
  } catch {
    return new Date().toLocaleString('en-US', formatOptions)
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
 * @param {boolean} includeSeconds - Whether to include seconds (default: false)
 * @returns {string} Formatted time string
 */
export function formatTime(timestamp, includeSeconds = false) {
  return formatTimestamp(timestamp, {
    hour: 'numeric',
    minute: 'numeric',
    ...(includeSeconds ? { second: 'numeric' } : {}),
    hour12: true
  })
}

/**
 * Format a timestamp as a date and time string in the configured timezone
 * @param {string|Date} timestamp - ISO string or Date object
 * @param {boolean} includeSeconds - Whether to include seconds (default: false)
 * @returns {string} Formatted date and time string
 */
export function formatDateTime(timestamp, includeSeconds = false) {
  return formatTimestamp(timestamp, {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    ...(includeSeconds ? { second: 'numeric' } : {}),
    hour12: true
  })
}

/**
 * Format a timestamp as a short date string (e.g., "Jan 15")
 * @param {string|Date} timestamp - ISO string or Date object
 * @returns {string} Formatted date string
 */
export function formatDateShort(timestamp) {
  return formatTimestamp(timestamp, {
    month: 'short',
    day: 'numeric'
  })
}

/**
 * Format a timestamp as a date with weekday (e.g., "Mon, Jan 15")
 * @param {string|Date} timestamp - ISO string or Date object
 * @returns {string} Formatted date string
 */
export function formatDateWithWeekday(timestamp) {
  return formatTimestamp(timestamp, {
    weekday: 'short',
    month: 'short',
    day: 'numeric'
  })
}

/**
 * Format a timestamp as a long date string (e.g., "Monday, January 15, 2024")
 * @param {string|Date} timestamp - ISO string or Date object
 * @returns {string} Formatted date string
 */
export function formatDateLong(timestamp) {
  return formatTimestamp(timestamp, {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  })
}

/**
 * Format a timestamp as a date and time with short date format
 * @param {string|Date} timestamp - ISO string or Date object
 * @returns {string} Formatted date and time string
 */
export function formatDateShortTime(timestamp) {
  return formatTimestamp(timestamp, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    hour12: true
  })
}




