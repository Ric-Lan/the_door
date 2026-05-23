package main

func Standalone() {}

func (s Shape) Draw() {}

type Shape struct {
    X int
}

type Drawable interface {
    Draw()
}
