<a href="https://www.buymeacoffee.com/cagatayuresin" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

# Odoo XMLRPC Wrapper

***
A small wrapper for oversimplifying CRUD operations and connecting to the Odoo External API
with the Python xmlrpc module.
***

## Index

- [Odoo XMLRPC Wrapper](#odoo-xmlrpc-wrapper)
  - [Index](#index)
  - [Getting Started](#getting-started)
    - [Installing via pip](#installing-via-pip)
    - [A Simple Connection](#a-simple-connection)
    - [CRUD Operations](#crud-operations)
      - [Create](#create)
      - [Read](#read)
      - [Update](#update)
      - [Delete](#delete)
    - [Miscellaneous](#miscellaneous)
      - [Search](#search)
      - [Search and Read](#search-and-read)
      - [Count](#count)
      - [Get Fields](#get-fields)
      - [Custom](#custom)
  - [A Little Detail](#a-little-detail)
    - [Bot Instance](#bot-instance)
    - [Active Model](#active-model)
  - [Contribution](#contribution)
  - [License](#license)

***

## Getting Started

### Installing via pip

```bash
pip install odoo-xmlrpc-wrapper
```

### A Simple Connection

```python
from odoo_xmlrpc_wrapper import odoo_xmlrpc_wrapper as oxw


HOST = "odoo.myhost.com"
DB = "my_test_db"
USERLOGIN = "mymailtologin@odoo.com"
PASSWORD = "mypass"

bot = oxw.Bot(HOST, DB, USERLOGIN, PASSWORD)
```

Prints:

```commandline
Successfully Logged
Name: Mitchell Admin
DB: my_test_db
HOST: https://odoo.myhost.com
VERSION: saas~16.1
```

### CRUD Operations

Once the model to be processed in the CRUD functions is entered, the following other
You do not need to specify the model again as long as the model does not change to
the operation functions.

#### Create

```python
bot.create("res.partner", {"name": "John Doe"})
```

#### Read

```python
bot.read(ids=[84], fields=["name"])
```

Returns: `[{"id": 84, "name": "John Doe"}]`

#### Update

```python
bot.update(the_id=84, the_obj={"name": "Jane Doe"})
```

#### Delete

```python
bot.delete(ids=[84])
```

### Miscellaneous

#### Search

```python
bot.search(constraints=[("name", "=", "Mitchell Admin")])
```

Returns:
`[2]`

#### Search and Read

```python
bot.search_read(constraints=[("name", "=", "Mitchell Admin")])
```

Returns: `[{'id': 2, 'name': 'Mitchell Admin'}]`

#### Count

```python
bot.count()
```

Returns: `78`

#### Get Fields

```python
bot.get_fields("res.partner.title", attributes=["type"])
```

Output:

```commandline
{
  "name": {"type": "char"},
  "shortcut": {"type": "char"},
  "id": {"type": "integer"},
  "display_name": {"type": "char"},
  "create_uid": {"type": "many2one"},
  "create_date": {"type": "datetime"},
  "write_uid": {"type": "many2one"},
  "write_date": {"type": "datetime"},
}
```

#### Custom

```python
bot.custom("my_custom.model", "my_custom_method")
```

Output:

```commandline
You'll see the return value if your method has a return!
```

## A Little Detail

### Bot Instance

```python
bot = oxw.Bot(HOST, DB, USERLOGIN, PASSWORD) # Simple Connection
bot = oxw.Bot(HOST, DB, USERLOGIN, PASSWORD, secured=False) # For http:// (no-ssl) (localhost)
bot = oxw.Bot(test=True) # For XMLRPC Tests from Odoo saas
```

If you are going to connect to a host with an unencrypted http protocol such as localhost,
`secured=False` must be specified.

`test=True` allows you to connect to one of Odoo's own xmlrpc test servers. Odoo assigns
you a random host, database, user and password from the demo servers. You don't need other
attributes when test option is selected.

### Active Model

The default model when a bot instance is initialized is `"res.users"`. So when you command
`bot.count()` it returns active users total as an integer.

You can assign the active model at any time with `bot.model = "model.name"` or when calling
any next method, such as `bot.count("res.partner")`

## Contribution

Feel free to contribute. This project needs a fine exception handling.

## License

[MIT License](https://en.wikipedia.org/wiki/MIT_License)

Copyright 2023 Cagatay URESIN

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the “Software”), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
PURPOSE AND NON INFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
