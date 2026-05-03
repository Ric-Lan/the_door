/**
 * User management controller.
 */
import { UserService } from './userService';

export class UserController {
    private userService: UserService;

    constructor() {
        this.userService = new UserService();
    }

    /** Handle GET /users request */
    async getUsers(): Promise<User[]> {
        return this.userService.findAll();
    }

    /** Handle POST /users request */
    async createUser(data: CreateUserDto): Promise<User> {
        return this.userService.create(data);
    }
}
