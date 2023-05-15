import xmlrpc.client


class Bot:
    """
    A bot class to rule them all.
    """

    def __init__(
        self,
        host: str = None,
        db: str = None,
        userlogin: str = None,
        password: str = None,
        secured: bool = True,
        test: bool = False,
    ) -> None:
        """
        Bot instance initializer: If test = True other arguments muted. For http:// secured = False

        Args:
            host (str, optional): The host 'odoo.yourhost.com'. Defaults to None.
            db (str, optional): Database to login. Defaults to None.
            userlogin (str, optional): Login string. Defaults to None.
            password (str, optional): Password. Defaults to None.
            secured (bool, optional): http:// or https://. Defaults to True.
            test (bool, optional): To use Odoo's own test servers. Defaults to False.
        """
        self.__test_info = (
            xmlrpc.client.ServerProxy("https://demo.odoo.com/start").start()
            if test
            else "Not Test"
        )
        self.HOST = self.__test_info["host"][8:] if test else host
        self.URL = (
            f"https://{self.HOST}/xmlrpc/2"
            if secured
            else f"http://{self.HOST}/xmlrpc/2"
        )
        self.DB = self.__test_info["database"] if test else db
        self.USERLOGIN = self.__test_info["user"] if test else userlogin
        self.__PASSWORD = self.__test_info["password"] if test else password
        self.model = None
        self.__common = xmlrpc.client.ServerProxy(f"{self.URL}/common")
        self.version = self.__common.version()
        self.uid = self.__common.authenticate(
            self.DB, self.USERLOGIN, self.__PASSWORD, {}
        )
        if not self.uid:
            raise Exception(
                f"Wrong one ({self.HOST}, {self.DB}, {self.USERLOGIN}, PASSWORD)"
            )
        self.__orm = xmlrpc.client.ServerProxy(f"{self.URL}/object")
        self.profile = self.read("res.users", ids=self.uid, fields=["name"])[0]
        self.name = self.profile["name"]
        self.successful = True
        if self.successful:
            print(self.status)

    def satus(self) -> str:
        return f"Successfully Logged\nName: {self.name}\nDB: {self.DB}\nHOST: {self.HOST}\nVERSION: {self.version['server_version']}"

    def search_read(
        self,
        model: str = None,
        constraints: list = None,
        fields: list = None,
        limit: int = None,
    ) -> list:
        """
        Searches with constraints amd reads the results fields.

        Args:
            model (str, optional): Model name. Defaults to None.
            constraints (list, optional): Search constraints. Defaults to None.
            fields (list, optional): Desired fields to read. Defaults to ["name"].
            limit (int, optional): Result limit. Defaults to None.

        Returns:
            list: A list of results as dicts with desired fields.
        """
        if model:
            self.model = model
        if fields is None:
            fields = ["name"]
        if constraints is None:
            constraints = [[]]
        else:
            constraints = [constraints]
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self.model,
            "search_read",
            constraints,
            {"fields": fields} if limit is None else {"fields": fields, "limit": limit},
        )

    def search(
        self,
        model: str = None,
        constraints: list = None,
        offset: int = None,
        limit: int = None,
    ) -> list:
        """
        Searches with constraints and returns results ids.

        Args:
            model (str, optional): Model name. Defaults to None.
            constraints (list, optional): Search constraints. Defaults to None.
            offset (int, optional): Offset. Defaults to None.
            limit (int, optional): Result limit. Defaults to None.

        Returns:
            list: A list of record ids as integers.
        """
        if model:
            self.model = model
        if constraints is None:
            constraints = [[]]
        else:
            constraints = [constraints]
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self.model,
            "search",
            constraints,
            {"offset": offset, "limit": limit}
            if offset and limit
            else {"offset": offset}
            if offset
            else {"limit": limit}
            if limit
            else {},
        )

    def count(self, model: str = None, constraints: list = None) -> int:
        """
        Length of records with constraints.

        Args:
            model (str, optional): Model name. Defaults to None.
            constraints (list, optional): Search constraints. Defaults to None.

        Returns:
            int: Count of records.
        """
        return len(self.search(model, constraints))

    def read(self, model: str = None, ids: list = None, fields: list = None) -> list:
        """
        Reads ids with desired fields.

        Args:
            model (str, optional): Model name. Defaults to None.
            ids (list, optional): List of ids to read. Defaults to None.
            fields (list, optional): Desired fields to read. Defaults to None.

        Returns:
            list: A list of results as dicts with desired fields.
        """
        if model:
            self.model = model
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self.model,
            "read",
            [ids],
            {"fields": fields} if fields else {},
        )

    def delete(self, model: str = None, ids: list = None) -> None:
        """
        ID list to delete.

        Args:
            model (str, optional): Model name. Defaults to None.
            ids (list, optional): List of ids to delete. Defaults to None.
        """
        if model:
            self.model = model
        self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self.model,
            "unlink",
            [ids] if isinstance(ids, list) else [[ids]],
        )

    def create(self, model: str = None, the_obj: dict = None) -> None:
        """
        Creates new record.

        Args:
            model (str, optional): Model name. Defaults to None.
            the_obj (dict, optional): The object as dict to create. Defaults to None.

        Raises:
            ValueError: No Object
        """
        if the_obj is None:
            raise ValueError("No Object")
        if model:
            self.model = model
        self.__orm.execute_kw(
            self.DB, self.uid, self.__PASSWORD, self.model, "create", [the_obj]
        )

    def update(
        self, model: str = None, the_id: int = None, the_obj: dict = None
    ) -> None:
        """
        Updates a record.

        Args:
            model (str, optional): Model name. Defaults to None.
            the_id (int, optional): The id as integer of the record. Defaults to None.
            the_obj (dict, optional): The object as dict to update. Defaults to None.

        Raises:
            ValueError: No ID
            ValueError: No Object
        """
        if id is None:
            raise ValueError("No ID")
        if the_obj is None:
            raise ValueError("No Object")
        if model:
            self.model = model
        self.__orm.execute_kw(
            self.DB, self.uid, self.__PASSWORD, self.model, "write", [[the_id], the_obj]
        )

    def get_fields(self, model: str = None, attributes: list = None) -> dict:
        """
        Model fields with desired infos.

        Args:
            model (str, optional): Model name. Defaults to None.
            attributes (list, optional): Desired attributes of the fields. Defaults to None.

        Returns:
            dict: Fields of the model.
        """
        if model:
            self.model = model
        return self.__orm.execute_kw(
            self.DB,
            self.uid,
            self.__PASSWORD,
            self.model,
            "fields_get",
            [],
            {"attributes": attributes} if attributes else {},
        )

    def custom(self, model: str = None, command: str = None, att=[[]]):
        """
        Triggering a method remotely.

        Args:
            model (str): Model name.
            command (str): Your custom command's name.
            att (list, optional): Sends attributes your custom method.

        Returns:
            Your method's return.
        """
        if model:
            self.model = model
        return self.__orm.execute_kw(
            self.DB, self.uid, self.__PASSWORD, self.model, command, att
        )
