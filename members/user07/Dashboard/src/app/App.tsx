import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

interface ThreatItem {
  id: number;
  title: string;
  source: string;
  datetime: string;
  keywords: string[];
}

interface DailyData {
  date: string;
  count: number;
}

interface HourlyData {
  hour: number;
  count: number;
}

interface SourceData {
  source: string;
  count: number;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export default function App() {
  const [query, setQuery] = useState('');
  const [threats, setThreats] = useState<ThreatItem[]>([]);
  const [filteredThreats, setFilteredThreats] = useState<ThreatItem[]>([]);
  const [keywordStats, setKeywordStats] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // 통계 데이터
  const [summaryStats, setSummaryStats] = useState({ total: 0, new_24h: 0, change_percent: 0 });
  const [dailyData, setDailyData] = useState<DailyData[]>([]);
  const [hourlyData, setHourlyData] = useState<HourlyData[]>([]);
  const [sourceData, setSourceData] = useState<SourceData[]>([]);

  // API에서 데이터 가져오기
  useEffect(() => {
    const fetchAllData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // 모든 데이터를 병렬로 가져오기
        const [threatsRes, summaryRes, dailyRes, hourlyRes, sourcesRes] = await Promise.all([
          fetch(`${API_URL}/threats`),
          fetch(`${API_URL}/stats/summary`),
          fetch(`${API_URL}/stats/daily`),
          fetch(`${API_URL}/stats/hourly`),
          fetch(`${API_URL}/stats/sources`)
        ]);

        // 위협 목록
        if (threatsRes.ok) {
          const result = await threatsRes.json();
          if (result.status === 'ok' && Array.isArray(result.data)) {
            const threats = result.data.map((item: any) => ({
              id: item.id,
              title: item.title,
              source: item.source,
              datetime: item.datetime,
              keywords: Array.isArray(item.keywords) 
                ? item.keywords 
                : (typeof item.keywords === 'string' 
                  ? item.keywords.split(',').map((k: string) => k.trim()).filter((k: string) => k)
                  : [])
            }));
            setThreats(threats);
            setFilteredThreats(threats);
          }
        }

        // 전체 통계
        if (summaryRes.ok) {
          const result = await summaryRes.json();
          if (result.status === 'ok') {
            setSummaryStats(result.data);
          }
        }

        // 날짜별 통계
        if (dailyRes.ok) {
          const result = await dailyRes.json();
          if (result.status === 'ok') {
            setDailyData(result.data);
          }
        }

        // 시간대별 통계
        if (hourlyRes.ok) {
          const result = await hourlyRes.json();
          if (result.status === 'ok') {
            setHourlyData(result.data);
          }
        }

        // 소스별 통계
        if (sourcesRes.ok) {
          const result = await sourcesRes.json();
          if (result.status === 'ok') {
            setSourceData(result.data);
          }
        }
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchAllData();
  }, []);

  // 키워드 통계 계산
  useEffect(() => {
    const stats: Record<string, number> = {};
    threats.forEach((t) => t.keywords.forEach((kw) => (stats[kw] = (stats[kw] ?? 0) + 1)));
    setKeywordStats(stats);
  }, [threats]);

  const handleSearch = () => {
    const term = query.trim().toLowerCase();
    if (!term) {
      setFilteredThreats(threats);
      return;
    }
    setFilteredThreats(
      threats.filter((t) =>
        t.title.toLowerCase().includes(term) ||
        t.source.toLowerCase().includes(term) ||
        t.keywords.some((kw) => kw.toLowerCase().includes(term))
      )
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const sortedKeywords = Object.entries(keywordStats).sort((a, b) => b[1] - a[1]);
  const COLORS = ['#7c3aed', '#00d9ff', '#ff3366', '#10b981', '#f59e0b'];

  return (
    <div className="min-h-screen bg-[#0a0e1a] p-6">
      <div className="max-w-[1400px] mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-[#f0f4f8] mb-2">🕵️‍♂️ 다크웹 위협 모니터링</h1>
          <p className="text-[#a0afc0]">실시간 다크웹 데이터 조회 및 분석</p>
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-4 mb-6 text-red-300">
            <span className="text-sm">⚠️ 경고: {error}</span>
          </div>
        )}

        <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6 mb-6">
          <div className="flex gap-3">
            <input
              className="flex-1 border border-[#2d3b56] bg-[#0e1524] px-4 py-2.5 rounded-lg text-[#f0f4f8] placeholder-[#7d8ba8] focus:outline-none focus:border-[#00d9ff]/60 focus:ring-1 focus:ring-[#00d9ff]/20"
              placeholder="검색어 입력 (예: samsung, korea)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              onClick={handleSearch}
              className="px-8 py-2.5 bg-[#7c3aed] border border-[#7c3aed] rounded-lg text-[#f0f4f8] font-semibold hover:bg-[#6d2ce0] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              검색
            </button>
          </div>
        </div>

        {/* 📊 수치 카드 (상단) */}
        {!loading && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6">
              <div className="text-[#a0afc0] text-sm mb-2">총 위협 감지 건수</div>
              <div className="text-3xl font-bold text-[#00d9ff]">{summaryStats.total}</div>
            </div>
            <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6">
              <div className="text-[#a0afc0] text-sm mb-2">최근 24시간 신규</div>
              <div className="text-3xl font-bold text-[#7c3aed]">{summaryStats.new_24h}</div>
            </div>
            <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6">
              <div className="text-[#a0afc0] text-sm mb-2">일일 변화율</div>
              <div className={`text-3xl font-bold ${summaryStats.change_percent >= 0 ? 'text-[#ff3366]' : 'text-[#10b981]'}`}>
                {summaryStats.change_percent >= 0 ? '+' : ''}{summaryStats.change_percent}%
              </div>
            </div>
          </div>
        )}

        {loading && (
          <div className="text-center py-20">
            <p className="text-[#a0afc0] text-lg">데이터 로딩 중...</p>
          </div>
        )}

        {!loading && (
          <>
            {/* 📈 차트 그리드 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {/* 일일 트렌드 차트 */}
              <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6">
                <h2 className="text-[#f0f4f8] text-lg font-bold mb-4">📊 일일 위협 트렌드 (30일)</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={dailyData}>
                    <defs>
                      <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#7c3aed" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2d3b56" />
                    <XAxis dataKey="date" stroke="#7d8ba8" style={{fontSize: '12px'}} />
                    <YAxis stroke="#7d8ba8" style={{fontSize: '12px'}} />
                    <Tooltip 
                      contentStyle={{backgroundColor: '#0e1524', border: '1px solid #1e2940', borderRadius: '8px'}}
                      labelStyle={{color: '#f0f4f8'}}
                    />
                    <Area type="monotone" dataKey="count" stroke="#7c3aed" fillOpacity={1} fill="url(#colorCount)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* 시간대별 분포 차트 */}
              <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6">
                <h2 className="text-[#f0f4f8] text-lg font-bold mb-4">⏰ 시간대별 분포 (7일)</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={hourlyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2d3b56" />
                    <XAxis dataKey="hour" stroke="#7d8ba8" style={{fontSize: '12px'}} />
                    <YAxis stroke="#7d8ba8" style={{fontSize: '12px'}} />
                    <Tooltip 
                      contentStyle={{backgroundColor: '#0e1524', border: '1px solid #1e2940', borderRadius: '8px'}}
                      labelStyle={{color: '#f0f4f8'}}
                    />
                    <Bar dataKey="count" fill="#00d9ff" radius={[8, 8, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* 상위 소스 분석 */}
              <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6">
                <h2 className="text-[#f0f4f8] text-lg font-bold mb-4">📌 상위 소스 분석</h2>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={sourceData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({source, count}: any) => `${source} (${count})`}
                      outerRadius={90}
                      fill="#8884d8"
                      dataKey="count"
                    >
                      {sourceData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip 
                      contentStyle={{backgroundColor: '#0e1524', border: '1px solid #1e2940', borderRadius: '8px'}}
                      labelStyle={{color: '#f0f4f8'}}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* 키워드 통계 */}
              <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6">
                <h2 className="text-[#f0f4f8] text-lg font-bold mb-4">🏷️ 키워드 통계</h2>
                <div className="space-y-3 max-h-[300px] overflow-y-auto">
                  {sortedKeywords.length === 0 ? (
                    <p className="text-[#a0afc0] text-sm">데이터가 없습니다.</p>
                  ) : (
                    sortedKeywords.slice(0, 10).map(([kw, count]) => (
                      <div key={kw}>
                        <div className="flex justify-between mb-1">
                          <span className="text-[#f0f4f8] text-sm font-semibold">{kw}</span>
                          <span className="text-[#a0afc0] text-sm">({count})</span>
                        </div>
                        <div className="h-2 bg-[#1a2236] rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-[#7c3aed] to-[#00d9ff]"
                            style={{ width: `${Math.min((count / Math.max(...Object.values(keywordStats), 1)) * 100, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* 최근 위협 목록 */}
            <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6">
              <h2 className="text-[#f0f4f8] text-lg font-bold mb-4 flex items-center gap-2">
                <span>📰</span>
                최근 확인된 위협 ({filteredThreats.length}건)
              </h2>
              <div className="space-y-3 max-h-[500px] overflow-y-auto">
                {filteredThreats.map((item) => (
                  <div key={item.id} className="bg-[#0a0e1a] border border-[#2d3b56] rounded-lg p-4 hover:border-[#7c3aed]/50 transition-all">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-[#f0f4f8] font-semibold text-lg">{item.title}</h3>
                      <div className="w-2 h-2 rounded-full bg-[#ff3366] animate-pulse mt-1"></div>
                    </div>
                    <div className="text-sm text-[#a0afc0] mb-3">{item.source} · {item.datetime}</div>
                    <div className="flex flex-wrap gap-2">
                      {item.keywords.map((kw) => (
                        <span
                          key={kw}
                          className="inline-block px-3 py-1 bg-[#7c3aed]/20 border border-[#7c3aed]/40 rounded-full text-xs text-[#00d9ff]"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
                {filteredThreats.length === 0 && (
                  <div className="text-center py-12">
                    <p className="text-[#a0afc0]">검색 결과가 없습니다.</p>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
