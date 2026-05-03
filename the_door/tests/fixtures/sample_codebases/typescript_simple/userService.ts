/**
 * User data access service.
 */
export class UserService {
    /** Find all users in the database */
    async findAll(): Promise<User[]> {
        return [];
    }

    /** Create a new user record */
    async create(data: CreateUserDto): Promise<User> {
        return { id: '1', ...data };
    }

    /** Delete a user by ID */
    async delete(id: string): Promise<void> {
        // TODO: Add soft-delete support
    }
}
