import { useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const StatusPage = () => {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [healthRes, statsRes] = await Promise.all([
          axios.get(`${API}/health`),
          axios.get(`${API}/stats`)
        ]);
        setHealth(healthRes.data);
        setStats(statsRes.data);
      } catch (e) {
        console.error("Error fetching data:", e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-r from-pink-500 to-purple-600 mb-6">
            <span className="text-4xl">🎂</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 tracking-tight font-['Manrope']">
            Birthday Organizer Bot
          </h1>
          <p className="text-lg text-purple-200 max-w-2xl mx-auto font-['Work_Sans']">
            A Telegram bot that eliminates manual coordination of birthday gift collections in teams
          </p>
        </div>

        {/* Bot Link */}
        <div className="flex justify-center mb-12">
          <a
            href="https://t.me/bithday_manager_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-3 bg-gradient-to-r from-blue-500 to-cyan-500 text-white px-8 py-4 rounded-full font-semibold text-lg hover:from-blue-600 hover:to-cyan-600 transition-all duration-300 shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40"
            data-testid="telegram-bot-link"
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.223-.535.223l.19-2.712 4.94-4.465c.215-.19-.047-.297-.332-.107l-6.107 3.846-2.633-.823c-.573-.178-.582-.573.12-.848l10.29-3.966c.477-.177.895.107.567 1.88z"/>
            </svg>
            Open Bot on Telegram
          </a>
        </div>

        {/* Status Cards */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
          {/* Health Status */}
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20" data-testid="health-card">
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-3 h-3 rounded-full ${health?.bot_active ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
              <span className="text-white/70 text-sm font-medium">Bot Status</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {loading ? '...' : health?.bot_active ? 'Active' : 'Inactive'}
            </p>
          </div>

          {/* Users */}
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20" data-testid="users-card">
            <div className="flex items-center gap-3 mb-4">
              <span className="text-xl">👥</span>
              <span className="text-white/70 text-sm font-medium">Total Users</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {loading ? '...' : stats?.total_users || 0}
            </p>
          </div>

          {/* Teams */}
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20" data-testid="teams-card">
            <div className="flex items-center gap-3 mb-4">
              <span className="text-xl">🏢</span>
              <span className="text-white/70 text-sm font-medium">Teams</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {loading ? '...' : stats?.total_teams || 0}
            </p>
          </div>

          {/* Events */}
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20" data-testid="events-card">
            <div className="flex items-center gap-3 mb-4">
              <span className="text-xl">🎉</span>
              <span className="text-white/70 text-sm font-medium">Active Events</span>
            </div>
            <p className="text-2xl font-bold text-white">
              {loading ? '...' : stats?.active_events || 0}
            </p>
          </div>
        </div>

        {/* Features */}
        <div className="bg-white/5 backdrop-blur-lg rounded-3xl p-8 border border-white/10">
          <h2 className="text-2xl font-bold text-white mb-8 text-center font-['Manrope']">How It Works</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard
              icon="1️⃣"
              title="Add to Group"
              description="Add the bot to your team's Telegram group. It will only post birthday announcements there."
            />
            <FeatureCard
              icon="2️⃣"
              title="Set Birthday"
              description="Each team member privately sets their birthday and wishlist in the bot."
            />
            <FeatureCard
              icon="3️⃣"
              title="Get Notified"
              description="2 weeks before a birthday, the bot announces a collection and notifies participants."
            />
            <FeatureCard
              icon="4️⃣"
              title="Vote & Contribute"
              description="Participants vote on wishlist items and mark their contributions privately."
            />
            <FeatureCard
              icon="5️⃣"
              title="Organize"
              description="One person becomes organizer to finalize the gift and coordinate payment."
            />
            <FeatureCard
              icon="6️⃣"
              title="Celebrate"
              description="On the birthday, the bot sends a fun greeting in the team chat!"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-12 text-white/50 text-sm">
          <p>Made with ❤️ for better team celebrations</p>
        </div>
      </div>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => (
  <div className="bg-white/5 rounded-xl p-5 hover:bg-white/10 transition-colors duration-300" data-testid={`feature-${title.toLowerCase().replace(/\s+/g, '-')}`}>
    <div className="text-3xl mb-3">{icon}</div>
    <h3 className="text-lg font-semibold text-white mb-2 font-['Manrope']">{title}</h3>
    <p className="text-white/60 text-sm font-['Work_Sans']">{description}</p>
  </div>
);

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<StatusPage />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
