import unittest

from app import fetch_filter_options


SAMPLE_HTML = """
<form id="zmqs">
  <select name="q.sammelbegrif.id">
    <option value="-1">Alle</option>
    <option value="330100">Frauenwochen</option>
  </select>
  <ul id="ulkategorieid">
    <li class="katlevel1 odd">
      <label for="q.kat.id.908119">Politik · Beteiligung
        <input name="q.kat.id" value="908119" type="checkbox">
      </label>
    </li>
    <li class="katlevel2 even">
      <label for="q.kat.id.908120">Vorträge · Diskussion
        <input name="q.kat.id" value="908120" type="checkbox">
      </label>
    </li>
  </ul>
</form>
"""


class TestFetchFilterOptions(unittest.TestCase):
    def test_extract_series_options(self) -> None:
        items = fetch_filter_options.extract_series_options(SAMPLE_HTML)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[1]["id"], "330100")
        self.assertEqual(items[1]["label"], "Frauenwochen")

    def test_extract_category_options(self) -> None:
        items = fetch_filter_options.extract_category_options(SAMPLE_HTML)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], "908119")
        self.assertEqual(items[0]["level"], "katlevel1")
        self.assertEqual(items[1]["level"], "katlevel2")


if __name__ == "__main__":
    unittest.main()
