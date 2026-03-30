import { useState, useEffect, useRef } from 'react';
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
  risk_score?: number;
  content?: string;
  detect_time?: string;
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

  // 리로드 및 필터 상태
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(300); // 5분
  const [selectedKeywords, setSelectedKeywords] = useState<string[]>([]);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date>(new Date());
  const [refreshing, setRefreshing] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 상세 보기 및 타이머
  const [selectedThreat, setSelectedThreat] = useState<ThreatItem | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [nextCrawlTime, setNextCrawlTime] = useState<Date | null>(null);
  const [timeUntilCrawl, setTimeUntilCrawl] = useState<string>('00:00');

  // API에서 데이터 가져오기
  const fetchAllData = async (showGlobalLoading = true) => {
    try {
      if (showGlobalLoading) setLoading(true);
      setRefreshing(true);
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
                  : []),
              risk_score: item.risk_score || 50,
              content: item.content || '',
              detect_time: item.detect_time
            }));
            setThreats(threats);
            setFilteredThreats(threats);
          }
        } else {
          throw new Error('위협 데이터를 불러올 수 없습니다');
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
        
        setLastRefreshTime(new Date());
      } catch (err) {
        console.error('Error fetching data:', err);
        setError('서버 연결 실패');
      } finally {
        if (showGlobalLoading) setLoading(false);
        setRefreshing(false);
      }
    };

  useEffect(() => {
    fetchAllData();
  }, []);

  // 자동 리로드 설정
  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(() => {
      fetchAllData(false); // 로딩 스피너 표시 안 함
    }, autoRefreshInterval * 1000);

    return () => clearInterval(interval);
  }, [autoRefresh, autoRefreshInterval]);

  // 키워드 통계 계산
  useEffect(() => {
    const stats: Record<string, number> = {};
    threats.forEach((t) => t.keywords.forEach((kw) => (stats[kw] = (stats[kw] ?? 0) + 1)));
    setKeywordStats(stats);
  }, [threats]);

  // 드롭다운 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };

    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [dropdownOpen]);

  // 자동 새로고침 시 타이머 초기화 (autoRefresh/interval 변경 감지, 또는 새로고침 완료 시)
  useEffect(() => {
    if (!autoRefresh) {
      setTimeUntilCrawl('00:00');
      return;
    }

    // 자동 새로고침이 켜졌을 때 타이머를 현재 시간 + 설정된 interval로 초기화
    const now = new Date();
    const nextTime = new Date(now.getTime() + autoRefreshInterval * 1000);
    setNextCrawlTime(nextTime);
  }, [autoRefresh, autoRefreshInterval, lastRefreshTime]);

  // 크롤링까지 남은 시간 타이머 (자동 새로고침이 켜졌을 때만)
  useEffect(() => {
    if (!autoRefresh || !nextCrawlTime) {
      setTimeUntilCrawl('00:00');
      return;
    }
    
    const updateTimer = () => {
      const now = new Date();
      const diff = nextCrawlTime.getTime() - now.getTime();
      
      if (diff > 0) {
        const totalSeconds = Math.floor(diff / 1000);
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        setTimeUntilCrawl(`${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`);
      } else {
        setTimeUntilCrawl('00:00');
      }
    };

    updateTimer();
    // 매초 업데이트
    const intervalId = setInterval(updateTimer, 1000);
    return () => clearInterval(intervalId);
  }, [nextCrawlTime, autoRefresh]);

  // 위협 상세 정보 가져오기
  const fetchThreatDetail = async (threatId: number) => {
    try {
      const res = await fetch(`${API_URL}/threats/${threatId}`);
      if (res.ok) {
        const result = await res.json();
        if (result.status === 'ok') {
          setSelectedThreat(result.data);
          setShowDetailModal(true);
          return;
        }
      }
    } catch (err) {
      console.error('Error fetching threat detail:', err);
    }
    
    // API 실패 시 필터링된 위협에서 찾기
    const threatFromList = filteredThreats.find(t => t.id === threatId);
    if (threatFromList) {
      setSelectedThreat({
        ...threatFromList,
        content: threatFromList.title,
        detect_time: threatFromList.datetime
      });
      setShowDetailModal(true);
    }
  };

  // 위험도에 따른 색상 반환
  const getRiskColor = (score: number = 50) => {
    if (score >= 80) return 'text-red-400'; // 위험
    if (score >= 60) return 'text-yellow-400'; // 주의
    return 'text-green-400'; // 안전
  };

  const getRiskBgColor = (score: number = 50) => {
    if (score >= 80) return 'bg-red-400/10 border-red-400/30';
    if (score >= 60) return 'bg-yellow-400/10 border-yellow-400/30';
    return 'bg-green-400/10 border-green-400/30';
  };

  // 검색 및 필터링
  const handleSearch = () => {
    const term = query.trim().toLowerCase();
    
    let filtered = threats;
    
    // 텍스트 검색
    if (term) {
      filtered = filtered.filter((t) =>
        t.title.toLowerCase().includes(term) ||
        t.source.toLowerCase().includes(term) ||
        t.keywords.some((kw) => kw.toLowerCase().includes(term))
      );
    }
    
    // 키워드 필터링 (선택된 키워드 중 하나라도 포함된 위협 표시)
    if (selectedKeywords.length > 0) {
      filtered = filtered.filter((t) =>
        t.keywords.some((kw) => selectedKeywords.includes(kw))
      );
    }
    
    setFilteredThreats(filtered);
  };

  // 필터 조건이 변경될 때마다 필터링
  useEffect(() => {
    handleSearch();
  }, [selectedKeywords, threats]);

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
        <div className="flex justify-between items-start mb-8">
          <div>
            <h1 className="text-3xl font-bold text-[#f0f4f8] mb-2">🕵️‍♂️ 다크웹 위협 모니터링</h1>
            <p className="text-[#a0afc0]">실시간 다크웹 데이터 조회 및 분석</p>
          </div>
          <div className="text-right">
            <div className="text-xs text-[#7d8ba8] mb-2">
              마지막 업데이트: {lastRefreshTime.toLocaleTimeString('ko-KR')}
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => fetchAllData(true)}
                disabled={refreshing}
                className="px-4 py-2 bg-[#00d9ff] border border-[#00d9ff] rounded-lg text-[#0a0e1a] font-semibold hover:bg-[#00c4e0] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {refreshing ? '✓ 새로고침 중...' : '🔄 지금 새로고침'}
              </button>
              <div className="flex items-center gap-2 bg-[#121824] border border-[#1e2940] rounded-lg px-3 py-2">
                <input
                  type="checkbox"
                  id="autoRefresh"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="w-4 h-4 cursor-pointer"
                />
                <label htmlFor="autoRefresh" className="text-sm text-[#f0f4f8] cursor-pointer select-none">
                  자동 새로고침
                </label>
                {autoRefresh && (
                  <select
                    value={autoRefreshInterval}
                    onChange={(e) => setAutoRefreshInterval(Number(e.target.value))}
                    className="text-xs bg-[#0e1524] border border-[#2d3b56] rounded px-2 py-1 text-[#f0f4f8] ml-2"
                  >
                    <option value={60}>1분</option>
                    <option value={300}>5분</option>
                    <option value={600}>10분</option>
                    <option value={1800}>30분</option>
                  </select>
                )}
              </div>
              <div className="text-xs text-[#7d8ba8] bg-[#121824] border border-[#1e2940] rounded-lg px-3 py-2">
                다음 수집까지: <span className="text-[#00d9ff] font-semibold">{timeUntilCrawl}</span>
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-4 mb-6 text-red-300">
            <span className="text-sm">⚠️ {error}</span>
          </div>
        )}

        {/* 검색 및 필터 섹션 */}
        <div className="bg-[#121824] border border-[#1e2940] rounded-xl p-6 mb-6">
          <div className="mb-4">
            <label className="text-sm text-[#a0afc0] block mb-3">🏷️ 키워드 필터</label>
            <div className="relative w-full max-w-md" ref={dropdownRef}>
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="w-full flex items-center justify-between border border-[#2d3b56] bg-[#0e1524] px-4 py-2.5 rounded-lg text-[#f0f4f8] hover:border-[#00d9ff]/60 transition-all"
              >
                <span className="text-sm">
                  {selectedKeywords.length === 0 
                    ? '키워드 선택 (전체)' 
                    : `${selectedKeywords.length}개 선택됨`}
                </span>
                <span className={`text-xs transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}>▼</span>
              </button>

              {dropdownOpen && (
                <div className="absolute top-full mt-1 w-full bg-[#0e1524] border border-[#2d3b56] rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto">
                  <div className="p-3 space-y-2">
                    {sortedKeywords.map(([keyword, count]) => (
                      <label key={keyword} className="flex items-center gap-2 p-2 hover:bg-[#1a2236] rounded cursor-pointer transition-all">
                        <input
                          type="checkbox"
                          checked={selectedKeywords.includes(keyword)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedKeywords([...selectedKeywords, keyword]);
                            } else {
                              setSelectedKeywords(selectedKeywords.filter(k => k !== keyword));
                            }
                          }}
                          className="w-4 h-4 cursor-pointer"
                        />
                        <span className="text-sm text-[#f0f4f8] select-none flex-1">{keyword}</span>
                        <span className="text-xs text-[#7d8ba8]">({count})</span>
                      </label>
                    ))}
                  </div>
                  {selectedKeywords.length > 0 && (
                    <div className="border-t border-[#1e2940] p-2">
                      <button
                        onClick={() => setSelectedKeywords([])}
                        className="w-full px-3 py-2 bg-[#1e2940] border border-[#2d3b56] rounded text-sm text-[#a0afc0] hover:text-[#f0f4f8] transition-all"
                      >
                        모두 초기화
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
            
            {selectedKeywords.length > 0 && (
              <div className="mt-3 flex gap-2 flex-wrap">
                <span className="text-xs text-[#a0afc0]">선택:</span>
                {selectedKeywords.map(kw => (
                  <span key={kw} className="inline-flex items-center gap-1 px-2 py-1 bg-[#7c3aed]/20 border border-[#7c3aed]/40 rounded-full text-xs text-[#00d9ff]">
                    {kw}
                    <button
                      onClick={() => setSelectedKeywords(selectedKeywords.filter(k => k !== kw))}
                      className="ml-1 hover:text-[#ff3366]"
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

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

        {!loading && error && (
          <div className="text-center py-20">
            <p className="text-[#ff3366] text-lg font-semibold mb-2">⚠️ 데이터를 불러올 수 없습니다</p>
            <p className="text-[#a0afc0]">{error}</p>
            <button
              onClick={() => fetchAllData(true)}
              className="mt-4 px-4 py-2 bg-[#7c3aed] rounded-lg text-[#f0f4f8] hover:bg-[#6d2ce0] transition-all"
            >
              다시 시도
            </button>
          </div>
        )}

        {!loading && !error && (
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
                  <div 
                    key={item.id} 
                    onClick={() => fetchThreatDetail(item.id)}
                    className={`bg-[#0a0e1a] border border-[#2d3b56] rounded-lg p-4 hover:border-[#7c3aed]/50 transition-all cursor-pointer hover:bg-[#0f1422] ${getRiskBgColor(item.risk_score)}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <h3 className="text-[#f0f4f8] font-semibold text-lg">{item.title}</h3>
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        <div className="px-3 py-1 rounded-full bg-[#0a0e1a] border">
                          <span className={`text-sm font-bold ${getRiskColor(item.risk_score)}`}>
                            {item.risk_score || 50}
                          </span>
                        </div>
                        <div className="w-2 h-2 rounded-full bg-[#ff3366] animate-pulse"></div>
                      </div>
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
                    <div className="text-xs text-[#7d8ba8] mt-2">클릭하여 상세 정보 보기 →</div>
                  </div>
                ))}
                {filteredThreats.length === 0 && (
                  <div className="text-center py-12">
                    <p className="text-[#a0afc0]">검색 결과가 없습니다.</p>
                  </div>
                )}
              </div>
            </div>

            {/* 상세 보기 모달 */}
            {showDetailModal && selectedThreat && (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <div className="bg-[#121824] border border-[#1e2940] rounded-xl max-w-2xl w-full max-h-[85vh] overflow-y-auto">
                  <div className="p-6 border-b border-[#1e2940] flex justify-between items-start">
                    <div className="flex-1">
                      <h2 className="text-2xl font-bold text-[#f0f4f8] mb-2">{selectedThreat.title}</h2>
                      <div className="flex gap-3 items-center">
                        <div className={`px-3 py-1 rounded-full bg-[#0a0e1a] border ${getRiskBgColor(selectedThreat.risk_score)}`}>
                          <span className={`text-lg font-bold ${getRiskColor(selectedThreat.risk_score)}`}>
                            {selectedThreat.risk_score || 50}
                          </span>
                        </div>
                        <span className="text-sm text-[#7d8ba8]">{selectedThreat.source}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => setShowDetailModal(false)}
                      className="text-[#7d8ba8] hover:text-[#f0f4f8] text-2xl"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="p-6 space-y-4">
                    <div>
                      <h3 className="text-[#00d9ff] font-semibold mb-2">📅 탐지 시간</h3>
                      <p className="text-[#a0afc0]">{selectedThreat.datetime}</p>
                    </div>

                    <div>
                      <h3 className="text-[#00d9ff] font-semibold mb-2">📍 출처</h3>
                      <a href={selectedThreat.source} target="_blank" rel="noopener noreferrer" 
                        className="text-[#7c3aed] hover:text-[#00d9ff] underline truncate">
                        {selectedThreat.source}
                      </a>
                    </div>

                    <div>
                      <h3 className="text-[#00d9ff] font-semibold mb-2">🏷️ 키워드</h3>
                      <div className="flex flex-wrap gap-2">
                        {selectedThreat.keywords.map((kw) => (
                          <span
                            key={kw}
                            className="inline-block px-3 py-1 bg-[#7c3aed]/20 border border-[#7c3aed]/40 rounded-full text-xs text-[#00d9ff]"
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div>
                      <h3 className="text-[#00d9ff] font-semibold mb-2">📄 원문 내용</h3>
                      <div className="bg-[#0a0e1a] border border-[#2d3b56] rounded-lg p-4 max-h-[300px] overflow-y-auto">
                        <p className="text-[#a0afc0] text-sm whitespace-pre-wrap break-words">
                          {selectedThreat.content && selectedThreat.content.trim().length > 0 
                            ? selectedThreat.content 
                            : '상세 내용이 없습니다.'}
                        </p>
                      </div>
                    </div>

                    <div className="bg-[#0a0e1a] border border-[#2d3b56] rounded-lg p-4">
                      <h3 className="text-[#ff3366] font-semibold mb-2">⚠️ 위험도 분석</h3>
                      <p className="text-[#a0afc0] text-sm">
                        {selectedThreat.risk_score! >= 80 
                          ? '🔴 높은 위험: 즉시 조치가 필요합니다.'
                          : selectedThreat.risk_score! >= 60 
                          ? '🟡 중간 위험: 주의 깊게 모니터링하세요.'
                          : '🟢 낮은 위험: 정상 범위입니다.'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
