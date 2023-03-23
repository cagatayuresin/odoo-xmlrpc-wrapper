import unittest
from src.odoo_xmlrpc_wrapper import odoo_xmlrpc_wrapper as oxw


class TestOXW(unittest.TestCase):
    bot = oxw.Bot(test=True)

    def test_case_0(self):
        self.assertEqual(self.bot.successful, True)

    def test_case_1(self):
        self.bot.create("res.partner", {"name": "John Doe"})
        self.assertEqual(
            self.bot.search_read(constraints=[("name", "=", "John Doe")]),
            [{"id": 84, "name": "John Doe"}],
        )
        self.assertEqual(
            self.bot.search(constraints=[("name", "=", "John Doe")]),
            [84],
        )

    def test_case_2(self):
        self.bot.update(the_id=84, the_obj={"name": "Jane Doe"})
        self.assertEqual(
            self.bot.read(ids=[84], fields=["name"]), [{"id": 84, "name": "Jane Doe"}]
        )

    def test_case_3(self):
        self.assertEqual(self.bot.count(), 79)

    def test_case_4(self):
        self.assertDictEqual(
            self.bot.get_fields("res.partner.title", attributes=["type"]),
            {
                "name": {"type": "char"},
                "shortcut": {"type": "char"},
                "id": {"type": "integer"},
                "display_name": {"type": "char"},
                "create_uid": {"type": "many2one"},
                "create_date": {"type": "datetime"},
                "write_uid": {"type": "many2one"},
                "write_date": {"type": "datetime"},
            },
        )


if __name__ == "__main__":
    unittest.main()
