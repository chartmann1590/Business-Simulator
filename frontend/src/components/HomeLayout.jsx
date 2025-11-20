import ChatBubble from './ChatBubble'
import { getAvatarPath } from '../utils/avatarMapper'

function HomeLayout({ homeData, conversations = [], onOccupantClick }) {
  if (!homeData) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-gray-400">No home data available</div>
      </div>
    )
  }

  // Generate positions for occupants within the home
  const getOccupantPosition = (occupantIndex, totalOccupants) => {
    // Distribute occupants evenly across the home
    const cols = Math.ceil(Math.sqrt(Math.max(1, totalOccupants)))
    const row = Math.floor(occupantIndex / cols)
    const col = occupantIndex % cols
    
    // Position in percentage (with some padding from edges)
    const padding = 15
    const x = padding + (col * (100 - 2 * padding) / Math.max(1, cols - 1))
    const y = padding + (row * (100 - 2 * padding) / Math.max(1, cols - 1))
    
    return { x: Math.min(85, Math.max(15, x)), y: Math.min(85, Math.max(15, y)) }
  }

  const occupants = homeData.occupants || []
  const layoutImage = homeData.layout_image

  return (
    <div className="relative bg-white rounded-lg shadow-md overflow-hidden border-2 border-gray-200" style={{ minHeight: '500px' }}>
      {/* Home background image */}
      <div className="absolute inset-0 bg-gray-100">
        <img
          src={`/home_layout/${layoutImage}`}
          alt={homeData.view === 'exterior' ? 'Home Exterior' : 'Home Interior'}
          className="w-full h-full object-cover"
          onError={(e) => {
            console.error(`[HomeLayout] Failed to load home image: /home_layout/${layoutImage}`)
            e.target.style.display = 'none'
          }}
          onLoad={() => {
            console.log(`[HomeLayout] Successfully loaded home image: /home_layout/${layoutImage}`)
          }}
        />
      </div>
      
      {/* Home overlay with occupants */}
      <div className="relative z-10 h-full min-h-[500px]">
        {/* Home label and work hours indicator */}
        <div className="absolute top-2 left-2 bg-black bg-opacity-70 text-white text-xs font-semibold px-2 py-1 rounded flex items-center space-x-2">
          <span>{homeData.view === 'exterior' ? 'Exterior View' : 'Interior View'}</span>
          {homeData.is_work_hours && (
            <>
              <span className="text-gray-300">•</span>
              <span className="text-yellow-300">Employee at Office</span>
            </>
          )}
        </div>
        
        {/* Address label */}
        {homeData.home_address && (
          <div className="absolute top-2 right-2 bg-black bg-opacity-70 text-white text-xs px-2 py-1 rounded max-w-xs truncate">
            {homeData.home_address}
          </div>
        )}
        
        {/* Occupants */}
        {occupants.map((occupant, index) => {
          const position = occupant.position || getOccupantPosition(index, occupants.length)
          const isEmployee = occupant.type === 'employee'
          const isFamily = occupant.type === 'family'
          const isPet = occupant.type === 'pet'
          
          return (
            <div
              key={occupant.id}
              className="absolute z-20 cursor-pointer hover:scale-110 transition-transform duration-200"
              style={{
                left: `${position.x}%`,
                top: `${position.y}%`,
                transform: 'translate(-50%, -50%)'
              }}
              onClick={() => onOccupantClick && onOccupantClick(occupant)}
              title={occupant.name}
            >
              {/* Avatar */}
              <div className="relative">
                <img
                  src={
                    isEmployee
                      ? getAvatarPath(occupant)
                      : (occupant.avatar_path && occupant.avatar_path.startsWith('/')
                          ? occupant.avatar_path
                          : `/avatars/${occupant.avatar_path || 'office_char_01_manager.png'}`)
                  }
                  alt={occupant.name}
                  className={`rounded-full border-2 shadow-lg object-cover ${
                    isEmployee
                      ? 'w-12 h-12 border-blue-400'
                      : isFamily
                        ? 'w-10 h-10 border-green-400'
                        : 'w-10 h-10 border-yellow-400'
                  } ${occupant.sleep_state === 'sleeping' ? 'opacity-70' : ''}`}
                  onError={(e) => {
                    console.error(`[HomeLayout] Failed to load avatar for ${occupant.name}:`, occupant.avatar_path)
                    e.target.src = '/avatars/office_char_01_manager.png'
                  }}
                  onLoad={() => {
                    console.log(`[HomeLayout] Successfully loaded avatar for ${occupant.name}`)
                  }}
                />
                {/* Sleep indicator */}
                {occupant.sleep_state === 'sleeping' && (
                  <div className="absolute -top-2 -right-2 bg-blue-500 text-white rounded-full w-8 h-8 flex items-center justify-center shadow-lg text-lg animate-pulse">
                    💤
                  </div>
                )}
                {/* Name label */}
                <div className="absolute -bottom-6 left-1/2 transform -translate-x-1/2 bg-black bg-opacity-75 text-white text-xs px-2 py-1 rounded whitespace-nowrap">
                  {occupant.name}
                  {isFamily && occupant.relationship_type && (
                    <span className="text-gray-300 ml-1">({occupant.relationship_type})</span>
                  )}
                  {occupant.sleep_state === 'sleeping' && (
                    <span className="text-blue-300 ml-1">[Sleeping]</span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
        
        {/* Chat bubbles for conversations */}
        {conversations.map((conversation, convIndex) => {
          const messages = conversation.messages || []
          if (messages.length === 0) return null
          
          // Determine conversation type: employee-family or family-family
          let speakerOccupant = null
          let speakerName = null
          
          if (conversation.employee_id && conversation.family_member_id) {
            // Employee-family conversation
            const employeeOccupant = occupants.find(o => o.type === 'employee' && o.id === conversation.employee_id)
            const familyOccupant = occupants.find(o => o.type === 'family' && o.id === conversation.family_member_id)
            
            if (!employeeOccupant || !familyOccupant) return null
            
            // Show the last message in the conversation
            const lastMessage = messages[messages.length - 1]
            const isEmployeeSpeaking = lastMessage.speaker === conversation.employee_name
            speakerOccupant = isEmployeeSpeaking ? employeeOccupant : familyOccupant
            speakerName = lastMessage.speaker
          } else if (conversation.family_member1_id && conversation.family_member2_id) {
            // Family-family conversation
            const fm1Occupant = occupants.find(o => o.type === 'family' && o.id === conversation.family_member1_id)
            const fm2Occupant = occupants.find(o => o.type === 'family' && o.id === conversation.family_member2_id)
            
            if (!fm1Occupant || !fm2Occupant) return null
            
            // Show the last message in the conversation
            const lastMessage = messages[messages.length - 1]
            const isFm1Speaking = lastMessage.speaker === conversation.family_member1_name
            speakerOccupant = isFm1Speaking ? fm1Occupant : fm2Occupant
            speakerName = lastMessage.speaker
          } else {
            return null
          }
          
          if (!speakerOccupant) return null
          
          const speakerPosition = speakerOccupant.position || getOccupantPosition(
            occupants.findIndex(o => o.id === speakerOccupant.id),
            occupants.length
          )
          
          // Position bubble above the speaker
          const bubblePos = {
            x: speakerPosition.x,
            y: speakerPosition.y - 30
          }
          
          const lastMessage = messages[messages.length - 1]
          
          return (
            <ChatBubble
              key={`${convIndex}-${messages.length}`}
              message={lastMessage.text}
              speaker={speakerName}
              employeeId={speakerOccupant.id}
              position={bubblePos}
              isVisible={true}
            />
          )
        })}
        
        {/* Empty state */}
        {occupants.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-gray-400 text-sm bg-white bg-opacity-75 px-4 py-2 rounded">
              {homeData.is_work_hours 
                ? 'Employee is at the office during work hours (7am-7pm Mon-Fri)'
                : `No one is ${homeData.view_location || 'inside'} right now`}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default HomeLayout

