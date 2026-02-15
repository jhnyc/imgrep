import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom';
import KonvaPage from './components/KonvaPage';
import WebGLPage from './components/WebGLPage';

function AppContent() {
  const location = useLocation();
  const isWebGL = location.pathname === '/webgl';

  return (
    <>
      {/* Mode Switcher */}
      <div className="fixed bottom-4 left-4 z-50 bg-white/90 backdrop-blur border rounded-full px-4 py-2 shadow-lg flex gap-4 text-sm font-medium">
        <Link
          to="/"
          className={`hover:text-primary transition-colors ${isWebGL ? 'text-blue-600 font-bold' : 'text-gray-500'}`}
        >
          Konva (2D)
        </Link>
        <div className="w-px bg-gray-300"></div>
        <Link
          to="/webgl"
          className={`hover:text-primary transition-colors ${isWebGL ? 'text-purple-600 font-bold' : 'text-gray-500'}`}
        >
          WebGL (Pixi)
        </Link>
      </div>

      <Routes>
        <Route path="/" element={<KonvaPage />} />
        <Route path="/webgl" element={<WebGLPage />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
