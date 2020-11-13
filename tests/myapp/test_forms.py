from django.forms.models import modelform_factory
from myapp.models import Category, Genre, ReferencingModel
from myapp.tests import TreeTestCase

from mptt.forms import (
    MoveNodeForm,
    MPTTAdminForm,
    TreeNodeChoiceField,
    TreeNodeMultipleChoiceField,
)


class TestForms(TreeTestCase):
    fixtures = ["categories.json", "genres.json"]

    def test_adminform_instantiation(self):
        # https://github.com/django-mptt/django-mptt/issues/264
        c = Category.objects.get(name="Nintendo Wii")
        CategoryForm = modelform_factory(
            Category,
            form=MPTTAdminForm,
            fields=("name", "parent"),
        )
        self.assertTrue(CategoryForm(instance=c))

        # Test that the parent field is properly limited. (queryset)
        form = CategoryForm(
            {
                "name": c.name,
                "parent": c.children.all()[0].pk,
            },
            instance=c,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("Select a valid choice", "%s" % form.errors)

        # Test that even though we remove the field queryset limit,
        # validation still fails.
        form = CategoryForm(
            {
                "name": c.name,
                "parent": c.children.all()[0].pk,
            },
            instance=c,
        )
        form.fields["parent"].queryset = Category.objects.all()
        self.assertFalse(form.is_valid())
        self.assertIn("Invalid parent", "%s" % form.errors)

    def test_field_types(self):
        ReferencingModelForm = modelform_factory(ReferencingModel, exclude=("id",))

        form = ReferencingModelForm()

        # Also check whether we have the correct form field type
        self.assertTrue(isinstance(form.fields["fk"], TreeNodeChoiceField))
        self.assertTrue(isinstance(form.fields["one"], TreeNodeChoiceField))
        self.assertTrue(isinstance(form.fields["m2m"], TreeNodeMultipleChoiceField))

    def test_movenodeform_save(self):
        c = Category.objects.get(pk=2)
        form = MoveNodeForm(
            c,
            {
                "target": "5",
                "position": "first-child",
            },
        )
        self.assertTrue(form.is_valid())
        form.save()

        self.assertTreeEqual(
            Category.objects.all(),
            """
            1 - 1 0 1 20
            5 1 1 1 2 13
            2 5 1 2 3 8
            3 2 1 3 4 5
            4 2 1 3 6 7
            6 5 1 2 9 10
            7 5 1 2 11 12
            8 1 1 1 14 19
            9 8 1 2 15 16
            10 8 1 2 17 18
        """,
        )

    def test_movenodeform(self):
        self.maxDiff = 2000
        form = MoveNodeForm(Genre.objects.get(pk=7))
        expected = (
            '<tr><th><label for="id_target">Target:</label></th>'
            '<td><select name="target" size="10" id="id_target" required>'
            '<option value="" selected>---------</option>'
            '<option value="1"> Action</option>'
            '<option value="2">--- Platformer</option>'
            '<option value="3">------ 2D Platformer</option>'
            '<option value="4">------ 3D Platformer</option>'
            '<option value="5">------ 4D Platformer</option>'
            '<option value="6">--- Shootemup</option>'
            '<option value="8">------ Horizontal Scrolling Shootemup</option>'
            '<option value="9"> Role-playing Game</option>'
            '<option value="10">--- Action RPG</option>'
            '<option value="11">--- Tactical RPG</option>'
            "</select></td></tr>"
            '<tr><th><label for="id_position">Position:</label></th>'
            '<td><select name="position" id="id_position">'
            '<option value="first-child">First child</option>'
            '<option value="last-child">Last child</option>'
            '<option value="left">Left sibling</option>'
            '<option value="right">Right sibling</option>'
            "</select></td></tr>"
        )
        self.assertHTMLEqual(str(form), expected)
        form = MoveNodeForm(
            Genre.objects.get(pk=7), level_indicator="+--", target_select_size=5
        )
        self.assertIn('size="5"', str(form["target"]))
        self.assertInHTML(
            '<option value="3">+--+-- 2D Platformer</option>', str(form["target"])
        )
        form = MoveNodeForm(
            Genre.objects.get(pk=7), position_choices=(("left", "left"),)
        )
        self.assertHTMLEqual(
            str(form["position"]),
            (
                '<select id="id_position" name="position">'
                '<option value="left">left</option>'
                "</select>"
            ),
        )

    def test_treenodechoicefield(self):
        field = TreeNodeChoiceField(queryset=Genre.objects.all())
        self.assertHTMLEqual(
            field.widget.render("test", None),
            '<select name="test">'
            '<option value="" selected>---------</option>'
            '<option value="1"> Action</option>'
            '<option value="2">--- Platformer</option>'
            '<option value="3">------ 2D Platformer</option>'
            '<option value="4">------ 3D Platformer</option>'
            '<option value="5">------ 4D Platformer</option>'
            '<option value="6">--- Shootemup</option>'
            '<option value="7">------ Vertical Scrolling Shootemup</option>'
            '<option value="8">------ Horizontal Scrolling Shootemup</option>'
            '<option value="9"> Role-playing Game</option>'
            '<option value="10">--- Action RPG</option>'
            '<option value="11">--- Tactical RPG</option>'
            "</select>",
        )
        field = TreeNodeChoiceField(
            queryset=Genre.objects.all(), empty_label="None of the below"
        )
        self.assertInHTML(
            '<option value="" selected>None of the below</option>',
            field.widget.render("test", None),
        )

    def test_treenodechoicefield_level_indicator(self):
        field = TreeNodeChoiceField(queryset=Genre.objects.all(), level_indicator="+--")
        self.assertHTMLEqual(
            field.widget.render("test", None),
            '<select name="test">'
            '<option value="" selected>---------</option>'
            '<option value="1"> Action</option>'
            '<option value="2">+-- Platformer</option>'
            '<option value="3">+--+-- 2D Platformer</option>'
            '<option value="4">+--+-- 3D Platformer</option>'
            '<option value="5">+--+-- 4D Platformer</option>'
            '<option value="6">+-- Shootemup</option>'
            '<option value="7">+--+-- Vertical Scrolling Shootemup</option>'
            '<option value="8">+--+-- Horizontal Scrolling Shootemup</option>'
            '<option value="9"> Role-playing Game</option>'
            '<option value="10">+-- Action RPG</option>'
            '<option value="11">+-- Tactical RPG</option>'
            "</select>",
        )

    def test_treenodechoicefield_relative_level(self):
        top = Genre.objects.get(pk=2)
        field = TreeNodeChoiceField(queryset=top.get_descendants())
        self.assertHTMLEqual(
            field.widget.render("test", None),
            '<select name="test">'
            '<option value="" selected>---------</option>'
            '<option value="3">------ 2D Platformer</option>'
            '<option value="4">------ 3D Platformer</option>'
            '<option value="5">------ 4D Platformer</option>'
            "</select>",
        )

        field = TreeNodeChoiceField(
            queryset=top.get_descendants(include_self=True),
            start_level=top.level,
        )
        self.assertHTMLEqual(
            field.widget.render("test", None),
            '<select name="test">'
            '<option value="" selected>---------</option>'
            '<option value="2"> Platformer</option>'
            '<option value="3">--- 2D Platformer</option>'
            '<option value="4">--- 3D Platformer</option>'
            '<option value="5">--- 4D Platformer</option>'
            "</select>",
        )

        field = TreeNodeChoiceField(
            queryset=top.get_descendants(),
            start_level=top.level + 1,
        )
        self.assertHTMLEqual(
            field.widget.render("test", None),
            '<select name="test">'
            '<option value="" selected>---------</option>'
            '<option value="3"> 2D Platformer</option>'
            '<option value="4"> 3D Platformer</option>'
            '<option value="5"> 4D Platformer</option>'
            "</select>",
        )
