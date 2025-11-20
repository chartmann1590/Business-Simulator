# Office Simulation - Flutter Android App

A complete Flutter Android application that provides full access to the Office Simulation system through a beautiful, mobile-optimized interface.

## Features

- **Complete API Integration**: Access to all 88+ backend API endpoints
- **Real-time Updates**: WebSocket support for live data updates
- **Server Configuration**: Easy server connection setup with validation
- **Comprehensive Logging**: Built-in logging system with email export
- **All Features Accessible**:
  - Dashboard with business metrics
  - Employee management
  - Project and task tracking
  - Product catalog
  - Financial analytics
  - Office layout visualization
  - Communications (email & chat)
  - Meeting management
  - Customer reviews
  - Notifications
  - Pet care game
  - Shared drive
  - And more!

## Prerequisites

- Flutter SDK (3.9.2 or higher)
- Android Studio or VS Code with Flutter extensions
- Android device or emulator (API 21+)
- Office Simulation backend server running

## Setup

1. **Install Dependencies**:
   ```bash
   cd flutter_app
   flutter pub get
   ```

2. **Generate JSON Serialization Code**:
   ```bash
   flutter pub run build_runner build --delete-conflicting-outputs
   ```

3. **Run the App**:
   ```bash
   flutter run
   ```

## Configuration

### First Launch

On first launch, you'll be prompted to configure the server connection:

1. Enter your server URL (default: `http://localhost`)
2. Enter the server port (default: `8000`)
3. Click "Test Connection" to verify
4. Click "Save & Connect" to proceed

### Server Settings

- **Local Development**: Use `http://10.0.2.2:8000` for Android emulator
- **Local Network**: Use your computer's IP address (e.g., `http://192.168.1.100:8000`)
- **Remote Server**: Use the full server URL

## Project Structure

```
lib/
├── main.dart                 # App entry point
├── config/                   # Configuration files
├── models/                    # Data models
├── services/                  # Core services (API, WebSocket, Logger, Storage)
├── screens/                   # All app screens
│   ├── server_config_screen.dart
│   ├── home_screen.dart
│   ├── dashboard_screen.dart
│   ├── employees/
│   ├── projects/
│   ├── products/
│   ├── financials/
│   ├── office/
│   ├── communications/
│   ├── meetings/
│   ├── reviews/
│   ├── notifications/
│   ├── pets/
│   ├── shared_drive/
│   └── settings/
├── widgets/                   # Reusable widgets
├── providers/                 # State management
└── utils/                     # Utilities (formatters, validators, constants)
```

## Key Components

### Services

- **ApiService**: HTTP client for all API endpoints
- **WebSocketService**: Real-time updates via WebSocket
- **LoggerService**: Comprehensive logging with SQLite storage
- **StorageService**: Local storage using SharedPreferences

### State Management

Uses Provider for state management with providers for:
- Server configuration
- Employees data
- Projects data
- WebSocket connection
- Logger

## Logging

The app includes comprehensive logging:

- **Log Levels**: Debug, Info, Warning, Error
- **Log Categories**: API, WebSocket, User Actions, Errors, Navigation
- **Log Viewer**: Filter by level, category, and date
- **Email Export**: Export logs via email for troubleshooting

Access logs from Settings → View Logs

## Troubleshooting

### Connection Issues

1. **Cannot connect to server**:
   - Verify server is running
   - Check URL and port are correct
   - For emulator, use `10.0.2.2` instead of `localhost`
   - Check network connectivity

2. **WebSocket not connecting**:
   - Verify WebSocket endpoint is accessible
   - Check server WebSocket configuration
   - Review logs for connection errors

### Build Issues

1. **JSON Serialization Errors**:
   ```bash
   flutter pub run build_runner build --delete-conflicting-outputs
   ```

2. **Missing Dependencies**:
   ```bash
   flutter pub get
   ```

### Runtime Errors

1. Check the logs screen for detailed error information
2. Export logs and review for API/WebSocket errors
3. Verify server is running and accessible
4. Check Android permissions (Internet, Network State)

## Development

### Running in Debug Mode

```bash
flutter run
```

### Building Release APK

```bash
flutter build apk --release
```

### Code Generation

After modifying models, regenerate JSON serialization:

```bash
flutter pub run build_runner watch
```

## API Integration

All API endpoints from the backend are integrated. See `lib/services/api_service.dart` for the complete list of available methods.

## WebSocket Events

The app listens for the following WebSocket events:
- `activity`: New activity occurred
- `employee_update`: Employee status changed
- `project_update`: Project status changed
- `financial_update`: Financial transaction occurred
- `review_completed`: Employee review completed
- `notification`: New notification created
- `meeting_update`: Meeting status changed

## License

MIT License

## Support

For issues and questions:
- Check the troubleshooting section
- Review application logs
- Verify server configuration
- Check backend server logs
