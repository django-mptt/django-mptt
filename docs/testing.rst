===================
Testing MPTT models
===================


Using testing generators
========================

Using testing generators such as ``model_bakery`` is causing random tree fields values, which can cause unexpected behavior.
To prevent that the ``django-mptt.MPTTModel`` will throw an Exception if made through model_bakery in test environment unless
the ``MPTT_ALLOW_TESTING_GENERATORS`` setting is set to True.

You can set the ``MPTT_ALLOW_TESTING_GENERATORS`` setting to True in your Django testing settings.py file or by the ``@override_settings`` decorator for particular test.
You would probably also have to use recipe and explicitly set the appropriate fields for the model.

.. code-block:: python

    from django.test import override_settings
    from baker.recipe import Recipe

    @override_settings(MPTT_ALLOW_TESTING_GENERATORS=True)
    def test_mptt_allow_testing_generators(self):
        my_model_recipe = Recipe(MyMPTTModel, lft=None, rght=None)
        test_model_instance = my_model_recipe.make()
