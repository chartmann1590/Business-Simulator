import { useEffect, useState } from 'react'

function ChatBubble({ message, speaker, employeeId, position, isVisible }) {
  const [displayedText, setDisplayedText] = useState('')
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0)

  useEffect(() => {
    if (!isVisible || !message) {
      setDisplayedText('')
      setCurrentMessageIndex(0)
      return
    }

    // Reset when message changes
    setDisplayedText('')
    setCurrentMessageIndex(0)
    
    // Type out the message character by character
    let charIndex = 0
    const typingInterval = setInterval(() => {
      if (charIndex < message.length) {
        setDisplayedText(message.substring(0, charIndex + 1))
        charIndex++
      } else {
        clearInterval(typingInterval)
      }
    }, 30) // 30ms per character for smooth typing effect

    return () => clearInterval(typingInterval)
  }, [message, isVisible])

  if (!isVisible || !message) return null

  return (
    <div
      className="absolute z-30 pointer-events-none"
      style={{
        left: `${position.x}%`,
        top: `${position.y}%`,
        transform: 'translate(-50%, -100%)',
      }}
    >
      <div className="relative">
        {/* Chat bubble */}
        <div className="bg-white rounded-lg shadow-lg border-2 border-gray-200 px-3 py-2 max-w-xs">
          {/* Speaker name */}
          <div className="text-xs font-semibold text-gray-700 mb-1">
            {speaker}
          </div>
          {/* Message text */}
          <div className="text-sm text-gray-800">
            {displayedText}
            {displayedText.length < message.length && (
              <span className="animate-pulse">|</span>
            )}
          </div>
        </div>
        {/* Arrow pointing down to employee */}
        <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
          <div className="w-0 h-0 border-l-8 border-r-8 border-t-8 border-transparent border-t-white"></div>
        </div>
      </div>
    </div>
  )
}

export default ChatBubble



