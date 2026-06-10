from cache import Cache

class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None
    
    def remove(self):
        """remove current node from the linked list"""
        if self.prev:
            self.prev.next = self.next
        if self.next:
            self.next.prev = self.prev
        self.prev = None
        self.next = None
    
    def append(self, n):
        """Appends another node after it"""
        if not n:
            return
        n.next = self.next
        if self.next:
            self.next.prev = n
        n.prev = self
        self.next = n

class LRUCache(Cache):
    """
    @param: capacity: An integer
    """
    def __init__(self, capacity):
        # do intialization if necessary
        self.capacity = capacity
        self.data = {}
        self.head = Node(None, None) # dummy head
        self.tail = Node(None, None) # dummy tail
        self.head.append(self.tail)

    def _least_recent(self, n):
        n.remove()
        self.head.append(n)

    """
    @param: key: An integer
    @return: An integer
    """
    def get(self, key):
        # write your code here
        if key not in self.data:
            return -1
        n = self.data[key]
        self._least_recent(n)
        return n.value

    """
    @param: key: An integer
    @param: value: An integer
    @return: nothing
    """
    def set(self, key, value):
        if self.capacity == 0:
            return
        # write your code here
        if key not in self.data:
            n = Node(key, value)
            self.data[key] = n
            if len(self.data) > self.capacity:
                toRemove = self.tail.prev
                toRemove.remove()
                del self.data[toRemove.key]
        n = self.data[key]
        n.value = value
        self._least_recent(n)

    def reset(self, capacity):
        self.__init__(capacity)