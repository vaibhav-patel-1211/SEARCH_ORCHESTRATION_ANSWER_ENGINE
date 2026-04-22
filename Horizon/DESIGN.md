# AI Chat UI Design Document

## 1. Goal
Recreate the clean, modern AI chat interface from the provided screenshots using React and Vanilla CSS. The UI features a sidebar, a top navigation bar, and two main views: a "Home" dashboard and a "Chat" conversation view.

## 2. Visual Aesthetic
- **Background**: Soft, large-scale radial gradient (warm peaches and light creams).
- **Layout**: Sidebar (left), Main Content (right), Top Navigation.
- **Components**:
    - High-quality, rounded containers with subtle borders/shadows.
    - Minimalist icons (using `lucide-react`).
    - Interactivity: Hover states, view switching.
- **Typography**: Clean, sans-serif font (Inter or system default).

## 3. Component Architecture
- `App.jsx`: State management for `activeView` ('home' | 'chat') and layout shell.
- `Sidebar.jsx`: 
    - Top: New chat, Search, Customize.
    - Middle: Navigation (Chats, Projects, Tasks, Agents, Companies).
    - Recents: List of previous chats.
    - Bottom: User profile card.
- `TopBar.jsx`: View-switcher tabs (Chats, Colab, Code) and window controls.
- `HomeView.jsx`: 
    - Centered content: Upgrade badge, Greeting ("Good afternoon, Lukas").
    - Input bar: Prompt box with attachments and model selector.
    - Quick Start cards: Grid of 4 task-based cards.
- `ChatView.jsx`: 
    - Content area: Rendered conversation about "Quantum Entanglement".
    - Footer: Fixed or floating chat input.

## 4. Technical Stack
- **Framework**: React 19.
- **Styling**: Vanilla CSS.
- **Icons**: `lucide-react`.
- **Build Tool**: Vite.

## 5. Implementation Roadmap
1. **Setup**: Install `lucide-react`.
2. **Global Styles**: Define variables (colors, gradients) and resets in `index.css`.
3. **Layout**: Create the main shell with sidebar and content area in `App.jsx`.
4. **Sidebar**: Implement the sidebar with all sections.
5. **TopBar**: Implement the navigation tabs.
6. **HomeView**: Create the landing page with Quick Start cards.
7. **ChatView**: Create the conversation view with formatted text content.
8. **Interactivity**: Connect sidebar/topbar to switch between views.
9. **Final Polishing**: Refine shadows, spacing, and responsive behavior.
