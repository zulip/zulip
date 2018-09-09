
class Component:
    def __init__(self, kind, name):
        self.ownees = []
        self.kind = kind
        self.name = name
        self.owner = None
        self.the_full_name =  "the.%s('%s')" % (self.kind, self.name)

    def owns(self, *ownees):
        assert not self.ownees
        for ownee in ownees:
            assert ownee.owner is None
            if ownee.kind == 'handlebars':
                assert self.kind == 'js_module'
        self.ownees = ownees
        for ownee in ownees:
            ownee.owner = self

class ComponentFactory:
    def __init__(self):
        self.store = {}

    def handlebars(self, name):
        return self._find('handlebars', name)

    def html_class(self, name):
        return self._find('html_class', name)

    def js_module(self, name):
        return self._find('js_module', name)

    def virtual_component(self, name):
        return self._find('virtual_component', name)

    def app(self, name):
        return self._find('app', name)

    def _find(self, kind, name):
        if (kind, name) not in self.store:
            self.store[(kind, name)] = self._make(kind, name)
        return self.store[(kind, name)]

    def _make(self, kind, name):
        return Component(kind=kind, name=name)
