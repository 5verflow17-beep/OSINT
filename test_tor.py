import requests

def check_tor():
    # 서버에 설정된 Tor Proxy (9050 포트) 사용
    proxies = {
        'http': 'socks5h://localhost:9050',
        'https': 'socks5h://localhost:9050'
    }
    
    try:
        # Tor 연결 확인 사이트 접속
        response = requests.get('https://check.torproject.org/api/ip', proxies=proxies, timeout=10)
        print("Tor 연결 성공!")
        print(f"현재 IP: {response.text}")
    except Exception as e:
        print(f"연결 실패: {e}")

if __name__ == "__main__":
    check_tor()