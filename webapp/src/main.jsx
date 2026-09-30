import React from 'react';
import ReactDOM from 'react-dom/client';
import {Theme} from '@astryxdesign/core';
import '@astryxdesign/core/reset.css';
import '@astryxdesign/core/astryx.css';
import './scientific.css';
import {floodWatchTheme} from './theme';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Theme theme={floodWatchTheme} mode="light">
      <App />
    </Theme>
  </React.StrictMode>,
);
