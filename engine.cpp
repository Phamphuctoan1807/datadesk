// DataDesk engine (C++17): đọc số/ngày, sắp xếp nhiều cấp, phát hiện trùng, so sánh số.
// Biên dịch: g++ -O2 -std=c++17 -shared -fPIC -o libddengine.so engine.cpp
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <numeric>
#include <string>
#include <unordered_map>
#include <vector>
#ifdef _WIN32
#define EXP extern "C" __declspec(dllexport)
#else
#define EXP extern "C" __attribute__((visibility("default")))
#endif
static inline bool dig(char c) { return c >= '0' && c <= '9'; }
static bool ci(const char* p, const char* lit) {
  for (; *lit; ++p, ++lit) if (!*p || (*p | 32) != *lit) return false;
  return true;
}
static int ws_len(const char* p) {  // khoảng trắng ASCII và Unicode (khớp \s của Python)
  unsigned char c = *p;
  if ((c >= 9 && c <= 13) || (c >= 28 && c <= 32)) return 1;
  if (!strncmp(p, "\xC2\xA0", 2) || !strncmp(p, "\xC2\x85", 2)) return 2;
  if (!strncmp(p, "\xE1\x9A\x80", 3) || !strncmp(p, "\xE2\x80\xA8", 3) || !strncmp(p, "\xE2\x80\xA9", 3) ||
      !strncmp(p, "\xE2\x80\xAF", 3) || !strncmp(p, "\xE2\x81\x9F", 3) || !strncmp(p, "\xE3\x80\x80", 3)) return 3;
  if (!strncmp(p, "\xE2\x80", 2) && (unsigned char)p[2] >= 0x80 && (unsigned char)p[2] <= 0x8A) return 3;
  return 0;
}
static bool grouped(const std::string& s, char sep) {  // [+-]?\d{1,3}(sep\d{3})+
  size_t i = 0, n = s.size();
  if (i < n && (s[i] == '+' || s[i] == '-')) i++;
  size_t a = i; while (i < n && dig(s[i])) i++;
  if (i == a || i - a > 3) return false;
  int g = 0;
  while (i < n) {
    if (s[i] != sep || i + 3 >= n || !dig(s[i + 1]) || !dig(s[i + 2]) || !dig(s[i + 3])) return false;
    i += 4; g++;
  }
  return g > 0;
}
static bool parse_num(const char* in, double& out) {
  std::string s;
  for (const char* p = in; *p;) {
    if (int w = ws_len(p)) { p += w; continue; }
    if (*p == '$' || *p == '%') { p++; continue; }
    if (!strncmp(p, "\xE2\x82\xAB", 3) || !strncmp(p, "\xE2\x82\xAC", 3)) { p += 3; continue; }
    if (!strncmp(p, "\xC4\x91", 2) || !strncmp(p, "\xC4\x90", 2)) { p += 2; continue; }
    if (ci(p, "vnd")) { p += 3; continue; }
    if (ci(p, "vn") && (!strncmp(p + 2, "\xC4\x91", 2) || !strncmp(p + 2, "\xC4\x90", 2))) { p += 4; continue; }
    s += *p++;
  }
  size_t n = s.size(), i = 0; bool any = false;
  if (!n) return false;
  if (s[0] == '+' || s[0] == '-') i = 1;
  for (; i < n; i++) { if (dig(s[i])) any = true; else if (s[i] != '.' && s[i] != ',') return false; }
  if (!any) return false;
  size_t hc = std::count(s.begin(), s.end(), ','), hd = std::count(s.begin(), s.end(), '.');
  auto erase = [&](char c) { s.erase(std::remove(s.begin(), s.end(), c), s.end()); };
  if (hc && hd) {
    char dec = s.rfind(',') > s.rfind('.') ? ',' : '.', th = dec == ',' ? '.' : ',';
    erase(th); std::replace(s.begin(), s.end(), dec, '.');
  } else if (hc) {
    if (grouped(s, ',')) erase(','); else if (hc > 1) return false; else std::replace(s.begin(), s.end(), ',', '.');
  } else if (hd) {
    if (grouped(s, '.')) erase('.'); else if (hd > 1) return false;
  }
  char* e; out = strtod(s.c_str(), &e);
  return e != s.c_str() && *e == 0;
}
static int rd(const char*& p, int& v) { int n = 0; v = 0; while (dig(*p)) { if (n < 9) v = v * 10 + (*p - '0'); n++; p++; } return n; }
static inline bool sepc(char c) { return c == '/' || c == '-' || c == '.'; }
static long dfc(long y, unsigned m, unsigned d) {  // số ngày kể từ 1970-01-01
  y -= m <= 2; long era = (y >= 0 ? y : y - 399) / 400; unsigned yoe = (unsigned)(y - era * 400);
  unsigned doy = (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + d - 1;
  unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + (long)doe - 719468;
}
static bool parse_date(const char* in, double& out) {  // dd/mm/yyyy hoặc yyyy-mm-dd; trả về thứ tự ngày như date.toordinal() của Python
  const char* p = in; while (int w = ws_len(p)) p += w;
  int a, b, c, y, m, d, la = rd(p, a);
  if (la >= 1 && la <= 2) {
    if (!sepc(*p)) return false; p++;
    int lb = rd(p, b); if (lb < 1 || lb > 2 || !sepc(*p)) return false; p++;
    if (rd(p, c) != 4) return false; d = a; m = b; y = c;
  } else if (la == 4) {
    if (!sepc(*p)) return false; p++;
    int lb = rd(p, b); if (lb < 1 || lb > 2 || !sepc(*p)) return false; p++;
    int lc = rd(p, c); if (lc < 1 || lc > 2) return false; y = a; m = b; d = c;
  } else return false;
  if (y < 1 || y > 9999 || m < 1 || m > 12 || d < 1) return false;
  static const int dm[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  int dim = dm[m - 1] + (m == 2 && ((y % 4 == 0 && y % 100 != 0) || y % 400 == 0));
  if (d > dim) return false;
  out = (double)(dfc(y, m, d) + 719163);
  return true;
}
static int natcmp(const char* a, const char* b) {  // so sánh tự nhiên: số theo giá trị, chữ theo byte UTF-8
  while (*a && *b) {
    bool da = dig(*a), db = dig(*b);
    if (da && db) {
      const char *pa = a, *pb = b;
      while (*pa == '0') pa++; while (*pb == '0') pb++;
      const char *ea = pa, *eb = pb; while (dig(*ea)) ea++; while (dig(*eb)) eb++;
      size_t la = ea - pa, lb = eb - pb;
      if (la != lb) return la < lb ? -1 : 1;
      int c = memcmp(pa, pb, la); if (c) return c < 0 ? -1 : 1;
      while (dig(*a)) a++; while (dig(*b)) b++;
    } else if (da != db) return da ? -1 : 1;
    else {
      while (*a && *b && !dig(*a) && !dig(*b)) {
        if (*a != *b) return (unsigned char)*a < (unsigned char)*b ? -1 : 1;
        a++; b++;
      }
    }
  }
  return *a ? 1 : (*b ? -1 : 0);
}
EXP int dd_version() { return 2; }
EXP void dd_parse(int n, const char* const* s, int mode, double* out, uint8_t* ok) {
  for (int i = 0; i < n; i++) { out[i] = 0; ok[i] = mode == 0 ? parse_num(s[i], out[i]) : parse_date(s[i], out[i]); }
}
// Sắp xếp ổn định nhiều cấp. Mỗi cấp: kind 0 = số/ngày, 1 = chữ (khóa chính pk rồi khóa phụ sk). Ô không hợp lệ luôn xếp cuối.
EXP int dd_sort(int n, int k, const int* kind, const int* desc, const double* num, const uint8_t* ok,
                const char* const* pk, const char* const* sk, int* out) {
  std::vector<int> idx(n); std::iota(idx.begin(), idx.end(), 0);
  std::stable_sort(idx.begin(), idx.end(), [&](int a, int b) {
    for (int j = 0; j < k; j++) {
      size_t oa = (size_t)j * n + a, ob = (size_t)j * n + b;
      bool va = ok[oa], vb = ok[ob];
      if (!va && !vb) continue; if (!va) return false; if (!vb) return true;
      int c;
      if (kind[j] == 0) { double x = num[oa], y = num[ob]; c = x < y ? -1 : (x > y ? 1 : 0); }
      else { c = natcmp(pk[oa], pk[ob]); if (!c) c = natcmp(sk[oa], sk[ob]); }
      if (c) return desc[j] ? c > 0 : c < 0;
    }
    return false;
  });
  for (int i = 0; i < n; i++) out[i] = idx[i];
  return 0;
}
EXP void dd_dups(int n, const char* const* keys, const uint8_t* ok, uint8_t* out) {
  std::unordered_map<std::string, int> m; m.reserve((size_t)n * 2);
  for (int i = 0; i < n; i++) if (ok[i]) m[keys[i]]++;
  for (int i = 0; i < n; i++) out[i] = ok[i] && m[keys[i]] > 1;
}
EXP void dd_contains(int n, const char* const* hay, const char* needle, uint8_t* out) {
  for (int i = 0; i < n; i++) out[i] = strstr(hay[i], needle) != nullptr;
}
EXP void dd_cmp(int n, const double* v, const uint8_t* ok, int op, double y, uint8_t* out) {
  for (int i = 0; i < n; i++) out[i] = ok[i] && (op == 0 ? v[i] > y : v[i] < y);
}
