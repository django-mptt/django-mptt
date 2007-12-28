def print_tree(tree, indent='  '):
    """
    Prints a nested tree with a given amount of indentation per level.
    """
    for node in tree:
        print '%s%s' % (indent * node.level, node)
