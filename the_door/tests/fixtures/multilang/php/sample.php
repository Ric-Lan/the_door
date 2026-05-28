<?php
class Greeter {
    /** Greet someone by name. */
    public function greet(string $name, int $times): string {
        return "hello " . $name;
    }
}
