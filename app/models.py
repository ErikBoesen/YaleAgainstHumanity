from app import app, db


class Game(db.Model):
    def __init__(self, group_id):
        """
        Start game.

        :param group_id: ID of group in which to create game.
        """
        self.group_id = group_id
        self.players = {}
        self.selection = []
        self.hand_size = 8
        self.build_decks()
        self.czar_user_id = None
        self.draw_black_card()

    def build_decks(self):
        """
        Generate black and white decks.
        """
        self.build_black_deck()
        self.build_white_deck()

    def build_black_deck(self):
        """
        Read black cards from file.
        """
        with open("resources/black.json", "r") as f:
            self.black_deck = json.load(f)
        # Filter out Pick 2 cards for now
        self.black_deck = [card for card in self.black_deck if card.count("_") == 1]
        self.black_deck = [card.replace("_", "_" * 5) for card in self.black_deck]
        random.shuffle(self.black_deck)

    def build_white_deck(self):
        """
        Read white cards from file.
        """
        with open("resources/white.json", "r") as f:
            self.white_deck = json.load(f)
        random.shuffle(self.white_deck)

    def draw_black_card(self):
        """
        Choose a random new black card from deck.
        """
        self.current_black_card = self.black_deck.pop()

    def appoint_czar(self, user_id=None):
        """
        Change who's Card Czar.

        :param user_id: ID of user to appoint as Czar. If not provided, a random player will be chosen.
        """
        if user_id is None:
            user_id = random.choice(list(self.players.keys()))
        self.czar_user_id = user_id

    def join(self, user_id, name):
        """
        Add a player to the game.

        :param user_id: ID of user to add.
        :param name: the user's name.
        """
        if user_id in self.players:
            return False
        self.players[user_id] = Player(user_id, name)
        self.deal(user_id)
        if self.czar_user_id is None:
            self.appoint_czar(user_id)
        return True

    def deal(self, user_id):
        """
        Fill a user's hand.

        :param user_id: ID of user to deal to.
        """
        for i in range(self.hand_size):
            self.deal_one(user_id)

    def deal_one(self, user_id):
        """
        Deal one white card to a specified user.

        :param user_id: ID of user to whom to deal.
        """
        self.players[user_id].draw_white(self.white_deck.pop())

    def has_played(self, user_id) -> bool:
        """
        Check whether a user has played a card already this round.

        :param user_id: ID of user to check.
        :return: whether user has played.
        """
        for candidate_id, card in self.selection:
            if candidate_id == user_id:
                return True
        return False

    def player_choose(self, user_id, card_index) -> bool:
        """
        Take a card from a user's hand and play it for the round.

        :param user_id: ID of user who's playing.
        :param card_index: index of card that user has chosen in their hand or selection.
        :return: if the player was allowed to choose their card; i.e. if they hadn't already played.
        """
        if self.has_played(user_id):
            return False
        card = self.players[user_id].hand.pop(card_index)
        self.selection.append((user_id, card))
        self.deal_one(user_id)
        return True

    def players_needed(self) -> int:
        """
        Check how many players need to play before cards can be flipped and Czar can judge.

        :return: number of players who have not played a card yet this round, excluding Czar.
        """
        return len(self.players) - len(self.selection) - 1

    def is_czar(self, user_id) -> bool:
        """
        Check if a user is the Czar.

        :param user_id: ID of user to check.
        :return: whether user is Czar.
        """
        return self.czar_user_id == user_id

    def get_nth_card_user_id(self, n):
        """
        Get which user submitted the nth card in selection.
        Useful when Czar chooses a card and only the index is sent.

        :param n: index of chosen card.
        :return: ID of user who played that card.
        """
        # TODO: this relies on dictionaries staying in a static order, which they do NOT necessarily!
        # Use a less lazy implementation.
        counter = 0
        for user_id, card in self.selection:
            if counter == n:
                return user_id, card
            counter += 1

    def czar_choose(self, card_index):
        """
        Choose the winner of a round.

        :param card_index: index of the card the Czar selected.
        :return: Text of card played, and the Player who played it.
        """
        user_id, card = self.get_nth_card_user_id(card_index)
        self.players[user_id].score(self.current_black_card)
        self.draw_black_card()
        self.selection = []
        self.appoint_czar(user_id)
        # Return card and winner
        return card, self.players[user_id]


class Player(db.Model):

    def __init__(self, user_id, name):
        self.user_id = user_id
        self.name = name
        self.hand = []
        self.won = []

    def draw_white(self, card):
        self.hand.append(card)

    def score(self, card):
        self.won.append(card)
